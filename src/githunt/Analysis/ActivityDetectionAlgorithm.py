from datetime import datetime
from loguru import logger

from githunt.Classes.User import User

def sort_timestamps_per_day(timestamps: list[datetime]) -> dict[str, list[datetime]]:
    sorted_timestamps: dict[str, list[datetime]] = {}

    for timestamp in timestamps:
        day_name = timestamp.strftime("%A")
        sorted_timestamps.setdefault(day_name, []).append(timestamp) # Already sorted, no need to sort again

    return sorted_timestamps

def compute_average_bounds_per_day(sorted_timestamps: dict[str, list[datetime]]) -> dict[str, tuple[float, float]]:
    """
    Computes mean(min(T_x)) and mean(max(T_x)) for each x in weekdays, where T_x is the set of timestamps of the day throughout the user's activity.

    Index 0 is lower bound
    Index 1 is upper bound
    """

    average_bounds_per_day: dict[str, tuple[float, float]] = {}
    bounds_collection_per_day: dict[str, dict[str, list[float]]] = {}

    for day, timestamps in sorted_timestamps.items():
        for timestamp in timestamps:
            bound_type = timestamp.hour > 12 and "upper" or "lower"
            midnight_timestamp_day = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

            deltatime_day = timestamp.timestamp() - midnight_timestamp_day.timestamp()
            bounds_collection_per_day.setdefault(day, {}).setdefault(bound_type, []).append(deltatime_day)

        day_bounds = bounds_collection_per_day.setdefault(day, {})
        upper_timestamps, lower_timestamps = day_bounds.setdefault("upper", [0]), day_bounds.setdefault("lower", [0])

        upper_sum, upper_count = sum(upper_timestamps), len(upper_timestamps)
        lower_sum, lower_count = sum(lower_timestamps), len(lower_timestamps)

        upper_mean, lower_mean = upper_sum / upper_count if upper_count != 0 else 0, lower_sum / lower_count if lower_count != 0 else 0
        average_bounds_per_day[day] = (lower_mean, upper_mean)

    return average_bounds_per_day

def infer_activity(user: User) -> tuple[dict[str, float], dict[str, tuple[float, float]]]:
    logger.info("Inferring activity")

    logger.debug("Computing timestamps per day")
    timestamps_per_day = sort_timestamps_per_day(user.git_data.timestamps)

    logger.debug("Computing average min/max bounds per day")
    average_bounds_per_day = compute_average_bounds_per_day(timestamps_per_day)

    logger.debug("Computing percentage of activity per day")
    total_timestamps_count = 0
    for timestamps in timestamps_per_day.values():
        total_timestamps_count += len(timestamps)

    ratio_interactions_per_day = {
        day: len(timestamps) / total_timestamps_count for day, timestamps in timestamps_per_day.items()
    }

    logger.trace("Raw ratio_interactions_per_day: {}", ratio_interactions_per_day)
    logger.trace("Raw average_bounds_per_day: {}", average_bounds_per_day)

    return ratio_interactions_per_day, average_bounds_per_day
