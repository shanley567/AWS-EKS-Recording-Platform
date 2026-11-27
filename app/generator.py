import json
import logging
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread

import boto3
import yaml
from flask import Flask, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
    Gauge
)
from pathlib import Path

from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

BUCKET_NAME = "jsp-radio-recordings-bucket-2026-demo"

APP_DIR = Path(__file__).parent
STATIONS_FILE = APP_DIR / "stations.yaml"

OUTPUT_DIR = Path("/data/output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------
# TESTING CONFIGURATION
# ------------------------------------------------------------------

# Temporary fault injection used when validating
# RecordingGapDetected alerting.
#
# Set to:
#
# None
#
# for normal operation.
#
# Example:
#
# "station-004"
#
# to simulate a station that has stopped
# generating new recordings.
#
# FAULT_INJECTION_STATION = "station-004"
FAULT_INJECTION_STATION = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s"
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# STATION CONFIG LOADING
# ------------------------------------------------------------------


def load_stations() -> list[dict]:
    """
    Load station configuration from YAML.

    Expected format:

    stations:

      - id: station-001
        name: BBC Radio 1
        stream_url: https://example.com/radio1
        country: UK
        genre: Music
        enabled: true
        segment_duration_seconds: 60

    Stations are represented as configuration
    objects rather than simple strings.

    This enables future capabilities such as:

    - Real radio stream recording
    - Recording gap detection
    - Per-station monitoring
    - Station registry migration
    - Station-specific alerting
    - Controller-based recorder deployment
    """

    if not STATIONS_FILE.exists():
        raise FileNotFoundError(
            f"Station configuration file not found: {STATIONS_FILE}"
        )

    with open(
        STATIONS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = yaml.safe_load(file)

    if not config:
        raise ValueError(
            "stations.yaml is empty"
        )

    stations = config.get("stations", [])

    if len(stations) == 0:
        raise ValueError(
            "No stations configured in stations.yaml"
        )

    validated_stations = []

    for station in stations:

        # Ensure every station provides the minimum
        # metadata required by the platform.
        #
        # These fields are intentionally validated
        # here so that bad configuration causes the
        # application to fail fast during startup.
        required_fields = [
            "id",
            "name",
            "stream_url",
            "country",
            "genre",
            "enabled",
            "segment_duration_seconds"
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in station
        ]

        if missing_fields:
            raise ValueError(
                f"Station "
                f"'{station.get('id', 'unknown')}' "
                f"is missing required fields: "
                f"{', '.join(missing_fields)}"
            )

        validated_stations.append(station)

    # Sort stations by id to ensure deterministic
    # processing order across restarts and deployments.
    return sorted(
        validated_stations,
        key=lambda station: station["id"]
    )


STATIONS = load_stations()

# ------------------------------------------------------------------
# AWS CLIENTS
# ------------------------------------------------------------------

s3 = boto3.client("s3")

# ------------------------------------------------------------------
# PROMETHEUS METRICS
# ------------------------------------------------------------------

recordings_generated_total = Counter(
    "recordings_generated_total",
    "Total recordings generated",
    ["station"]
)

s3_upload_success_total = Counter(
    "s3_upload_success_total",
    "Total successful S3 uploads",
    ["station"]
)

s3_upload_failure_total = Counter(
    "s3_upload_failure_total",
    "Total failed S3 uploads",
    ["station"]
)

upload_duration_seconds = Histogram(
    "upload_duration_seconds",
    "Time spent uploading files to S3",
    ["station"]
)

generation_cycle_duration_seconds = Histogram(
    "generation_cycle_duration_seconds",
    "Time taken to complete a generation cycle"
)

latest_recording_timestamp = Gauge(
    "latest_recording_timestamp",
    "Unix timestamp of latest generated recording",
    ["station"]
)

latest_successful_upload_timestamp = Gauge(
    "latest_successful_upload_timestamp",
    "Unix timestamp of latest successful S3 upload",
    ["station"]
)

spool_files_pending = Gauge(
    "spool_files_pending",
    "Files waiting for upload"
)

upload_retries_total = Counter(
    "upload_retries_total",
    "Total upload retries"
)

spool_oldest_file_age_seconds = Gauge(
    "spool_oldest_file_age_seconds",
    "Age of oldest file in spool"
)

# ----------------------------------------------------------
# Initialise upload timestamp metrics.
#
# This keeps metric series visible even if uploads stop.
# ----------------------------------------------------------

initial_timestamp = time.time()

for station in STATIONS:

    latest_successful_upload_timestamp.labels(
        station=station["id"]
    ).set(
        initial_timestamp
    )

# ------------------------------------------------------------------
# FLASK APP
# ------------------------------------------------------------------

app = Flask(__name__)


@app.route("/health/live")
def live():
    """
    Liveness probe.
    Confirms process is running.
    """

    return Response(
        "OK",
        status=200
    )


@app.route("/health/ready")
def ready():
    """
    Readiness probe.
    """

    return Response(
        "READY",
        status=200
    )


@app.route("/metrics")
def metrics():
    """
    Prometheus metrics endpoint.
    """

    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST
    )


def start_web_server():
    """
    Start Flask endpoints.
    """

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False,
        use_reloader=False
    )


# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------


def upload_file(
    filepath: Path,
    station: str
) -> None:
    """
    Upload a generated file to S3 using
    a date-partitioned structure.
    """

    current_time = datetime.now(UTC)

    object_key = (
        f"{station}/"
        f"{current_time.strftime('%Y/%m/%d/%H')}/"
        f"{filepath.name}"
    )

    logger.info(
        "Uploading file | station=%s bucket=%s key=%s",
        station,
        BUCKET_NAME,
        object_key
    )

    upload_start = time.time()

    s3.upload_file(
        str(filepath),
        BUCKET_NAME,
        object_key
    )

    upload_duration = time.time() - upload_start

    upload_duration_seconds.labels(
        station=station
    ).observe(upload_duration)

    logger.info(
        "Upload successful | station=%s key=%s duration_seconds=%.3f",
        station,
        object_key,
        upload_duration
    )

# ----------------------------------------------------------
# Creates retry metadata alongside a generated file.
#
# Metadata is used by the spool processor to determine
# when the next upload attempt should occur.
# ----------------------------------------------------------

def create_retry_metadata(
    metadata_path: Path
) -> None:

    metadata = {
        "retry_count": 0,
        "next_attempt": datetime.now(
            timezone.utc
        ).isoformat()
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2
        )
    )

# ----------------------------------------------------------
# Calculates exponential retry delay.
#
# Examples:
#
# retry 0 = 30 seconds
# retry 1 = 60 seconds
# retry 2 = 120 seconds
# retry 3 = 240 seconds
# ----------------------------------------------------------

def calculate_backoff_seconds(
    retry_count: int
) -> int:

    return min(
        30 * (2 ** retry_count),
        900
    )


# ----------------------------------------------------------
# Adds randomisation to retry timing.
#
# Prevents retry storms and thundering herd effects.
# ----------------------------------------------------------

def calculate_retry_delay(
    retry_count: int
) -> int:

    base_delay = calculate_backoff_seconds(
        retry_count
    )

    jitter = random.randint(
        0,
        base_delay // 2
    )

    return base_delay + jitter


# ----------------------------------------------------------
# Determines whether a file is eligible
# for another upload attempt.
# ----------------------------------------------------------

def should_retry(
    metadata_path: Path
) -> bool:

    metadata = json.loads(
        metadata_path.read_text()
    )

    next_attempt = datetime.fromisoformat(
        metadata["next_attempt"]
    )

    return (
        datetime.now(timezone.utc)
        >= next_attempt
    )

# ----------------------------------------------------------
# Upload retry handler
# ----------------------------------------------------------
def update_retry_metadata(
    metadata_path: Path
) -> None:

    metadata = json.loads(
        metadata_path.read_text()
    )

    metadata["retry_count"] += 1

    upload_retries_total.inc()

    retry_delay = calculate_retry_delay(
        metadata["retry_count"]
    )

    metadata["next_attempt"] = (
        datetime.now(
            timezone.utc
        ) +
        timedelta(
            seconds=retry_delay
        )
    ).isoformat()

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2
        )
    )


# ----------------------------------------------------------
# Background spool processor.
#
# Scans all files within the PVC-backed spool
# directory and uploads any retry-eligible files.
#
# Successful uploads remove both:
#
# - recording file
# - retry metadata file
#
# Failed uploads remain on disk and receive
# updated retry metadata.
# ----------------------------------------------------------

def process_spool() -> None:

    pending_count = 0

    oldest_file_age = 0

    for file_path in OUTPUT_DIR.rglob("*.json"):

        if file_path.name.endswith(
            ".metadata.json"
        ):
            continue

        metadata_path = file_path.with_suffix(
            ".metadata.json"
        )

        if not metadata_path.exists():
            continue

        pending_count += 1

        file_age = (
            time.time()
            - file_path.stat().st_mtime
        )

        oldest_file_age = max(
            oldest_file_age,
            file_age
        )

        if not should_retry(
            metadata_path
        ):
            continue

        station = file_path.parent.name

        logger.info(
            "Recording added to spool | station=%s file=%s",
            station_id,
            filename
)

# ------------------------------------------------------------------
# STARTUP
# ------------------------------------------------------------------

Thread(
    target=start_web_server,
    daemon=True
).start()

logger.info("===================================================")
logger.info("Synthetic Generator Starting")
logger.info("Bucket: %s", BUCKET_NAME)
logger.info("Stations Configured: %s", len(STATIONS))
logger.info(
    "Station List: %s",
    ", ".join(
        f"\n{station['id']} ({station['name']})"
        for station in STATIONS
    )
)
logger.info("Output Directory: %s", OUTPUT_DIR.absolute())
logger.info("Metrics Endpoint: http://0.0.0.0:8000/metrics")
logger.info("Liveness Endpoint: http://0.0.0.0:8000/health/live")
logger.info("Readiness Endpoint: http://0.0.0.0:8000/health/ready")
logger.info("Generation Interval: 60 seconds")
logger.info("===================================================")

# ------------------------------------------------------------------
# MAIN PROCESSING LOOP
# ------------------------------------------------------------------

while True:

    cycle_start = time.time()

    logger.info(
        "Generation cycle started | stations=%s",
        len(STATIONS)
    )

    for station in STATIONS:

        # ----------------------------------------------------------
        # Extract station metadata
        #
        # Stations are now represented as configuration
        # objects rather than simple strings.
        #
        # This metadata will support:
        #
        # - Real stream recording
        # - Recording gap detection
        # - Per-station dashboards
        # - Station registry migration
        # - Station-specific alerting
        # ----------------------------------------------------------

        station_id = station["id"]
        station_name = station["name"]
        country = station["country"]
        genre = station["genre"]

        # ----------------------------------------------------------
        # Allow stations to remain configured while
        # being operationally disabled.
        #
        # Future use cases:
        #
        # - Maintenance windows
        # - Stream decommissioning
        # - Temporary suspension
        # ----------------------------------------------------------

        if not station["enabled"]:

            logger.info(
                "Station skipped | station_id=%s enabled=false",
                station_id
            )

            continue

        payload = {

            # Unique station identifier used by the platform.
            "station_id": station_id,

            # Human-readable station metadata.
            "station_name": station_name,
            "country": country,
            "genre": genre,

            # Recording timestamp.
            "timestamp": datetime.now(
                UTC
            ).isoformat(),

            # Synthetic metric used to simulate
            # recording quality.
            "signal_strength": random.randint(
                80,
                100
            ),

            "status": "SUCCESS"
        }

        # ----------------------------------------------------------
        # Business-health tracking
        # These metrics enable future gap detection.
        # ----------------------------------------------------------

        current_timestamp = time.time()

        latest_recording_timestamp.labels(
            station=station_id
        ).set(
            current_timestamp
        )

        station_dir = OUTPUT_DIR / station_id

        station_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = station_dir / f"{int(time.time())}.json"

        metadata_file = (
            filename.with_suffix(".metadata.json")
        )

        create_retry_metadata(
            metadata_file
        )

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                payload,
                file
            )

        recordings_generated_total.labels(
            station=station_id
        ).inc()

        logger.info(
            (
                "Recording generated | "
                "station_id=%s "
                "station_name=%s "
                "country=%s "
                "genre=%s "
                "file=%s "
                "signal_strength=%s"
            ),
            station_id,
            station_name,
            country,
            genre,
            filename,
            payload["signal_strength"]
        )

        # ----------------------------------------------------------
        # Temporary fault injection.
        #
        # Simulates a recording gap for a single
        # station while the application and other
        # stations continue operating normally.
        #
        # Used only for alert validation.
        # ----------------------------------------------------------

        if (
            FAULT_INJECTION_STATION is not None
            and station_id == FAULT_INJECTION_STATION
        ):

            logger.warning(
                "Fault injection active | station_id=%s",
                station_id
            )

            continue
        

        try:

            upload_file(
                filename,
                station_id
            )

            s3_upload_success_total.labels(
                station=station_id
            ).inc()

            upload_timestamp = datetime.now(UTC).timestamp()

            latest_successful_upload_timestamp.labels(
                station=station_id
            ).set(
                upload_timestamp
            )

            logger.info(
                "Upload timestamp metric updated | station=%s timestamp=%s",
                station_id,
                upload_timestamp
            )


            # ------------------------------------------------------
            # Local files are removed only after a successful
            # upload to S3.
            #
            # This behaviour was validated during IRSA fault
            # testing where failed uploads remained available
            # inside the pod filesystem.
            #
            # Future production architecture should replace
            # pod-local storage with durable storage such as:
            #
            # - Amazon EFS
            # - Persistent Volumes
            #
            # to ensure failed uploads survive pod replacement.
            # ------------------------------------------------------

            filename.unlink()

            logger.info(
                "Local file deleted | station=%s file=%s",
                station_id,
                filename
            )

        except Exception as error:

            s3_upload_failure_total.labels(
                station=station_id
            ).inc()

            logger.exception(
                (
                    "Upload failed | "
                    "station_id=%s "
                    "station_name=%s "
                    "file=%s "
                    "error=%s"
                ),
                station_id,
                station_name,
                filename,
                str(error)
            )

    cycle_duration = round(
        time.time() - cycle_start,
        2
    )

    generation_cycle_duration_seconds.observe(
        cycle_duration
    )

    logger.info(
        (
            "Generation cycle completed | "
            "stations_processed=%s "
            "duration_seconds=%s"
        ),
        len(
            [
                station
                for station in STATIONS
                if station["enabled"]
            ]
        ),
        cycle_duration
    )

    logger.info(
    "Running spool processor"
    )

    process_spool()

    logger.info(
        "Sleeping before next cycle | sleep_seconds=60"
    )

    time.sleep(60)