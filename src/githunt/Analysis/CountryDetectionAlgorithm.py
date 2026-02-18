from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, available_timezones
from loguru import logger
from countryinfo import CountryInfo

import countryflag
import pytz

from githunt.Classes.User import User

def timezones_matching_offset(dt_utc: datetime, offset: timedelta) -> set[str]:
    matches: set[str] = set()

    for tz_name in available_timezones():
        try:
            tz = ZoneInfo(tz_name)
            dt_local = dt_utc.astimezone(tz)
            if dt_local.utcoffset() == offset:
                matches.add(tz_name)
        except Exception as e:
            logger.trace("Zone '{}' failed: {}", tz_name, e)

    logger.trace(
        "Offset {} at UTC {} matched {} timezones",
        offset,
        dt_utc,
        len(matches),
    )

    return matches

def infer_countries(user: User, N: int) -> list[dict]:
    logger.debug("Starting country detection (top {})", N)

    timestamps = user.git_data.timestamps
    total_timestamps = len(timestamps)

    if total_timestamps == 0:
        logger.warning("No timestamps available for user.")
        return []

    country_counter: dict[str, int] = {}

    for ts in timestamps:
        if ts.tzinfo is None:
            logger.warning("Naive timestamp detected: {}, assuming UTC", ts)
            ts = ts.replace(tzinfo=timezone.utc)

        offset = ts.utcoffset()
        if offset is None:
            logger.warning("Timestamp {} has no offset, skipping", ts)
            continue

        ts_utc = ts.astimezone(timezone.utc)
        tz_candidates = timezones_matching_offset(ts_utc, offset)

        if not tz_candidates:
            logger.trace(
                "No timezone candidates for timestamp {} (offset {})",
                ts,
                offset,
            )
            continue

        matched_any = False

        for country_code, tz_list in pytz.country_timezones.items():
            if any(tz in tz_candidates for tz in tz_list):
                country_counter[country_code] = (
                    country_counter.get(country_code, 0) + 1
                )
                matched_any = True

        if not matched_any:
            logger.trace(
                "No country matched timezone candidates for timestamp {}",
                ts,
            )

    if not country_counter:
        logger.warning("No countries matched any timestamps")
        return []

    logger.trace("Raw country match counts: {}", country_counter)

    # Population-weighted scoring
    country_scores: dict[str, float] = {}
    for country_code, count in country_counter.items():
        try:
            population: int = CountryInfo(country_code).population() # pyright: ignore[reportAssignmentType]
        except:
            logger.warning(
                "Failed retrieving population for country code '{}'",
                country_code,
            )
            population = 1
            continue

        score = count * (population ** 0.5)
        country_scores[country_code] = score

    if not country_scores:
        logger.warning("Country scoring failed; no valid scores")
        return []

    results: list[dict] = []
    total_score = sum(country_scores.values())

    for code, score in country_scores.items():
        probability = score / total_score if total_score > 0 else 0

        try:
            info = CountryInfo(code).info()
            assert info

            name = info.get("name", code)
            flag = countryflag.getflag(name)
        except:
            logger.exception("An error occurred while reading the country info")
            name, flag = code, 'X'

        results.append({
            "name": f"{flag}  {name}",
            "probability": probability,
        })

    logger.trace("Final country inference: {}", results)

    results.sort(key=lambda r: r["probability"], reverse=True)
    return results[:N]
