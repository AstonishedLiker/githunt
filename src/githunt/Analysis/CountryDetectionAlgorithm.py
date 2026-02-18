from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, available_timezones
from typing import Iterable, Optional
from loguru import logger
from countryinfo import CountryInfo

import pytz
import countryflag

from githunt.Classes.CountryResult import CountryResult

WAKE_START = 6
WAKE_END = 23 # Inclusive

def build_tz_to_country_map() -> dict[str, list[str]]:
    tz_to_countries: dict[str, list[str]] = {}
    for cc, tzs in pytz.country_timezones.items():
        for tz in tzs:
            tz_to_countries.setdefault(tz, []).append(cc)

    logger.debug("Built tz->country map for {} zone names", len(tz_to_countries))
    return tz_to_countries

TZ_TO_COUNTRY = build_tz_to_country_map()

def unique_utc_pairs(timestamps: Iterable[datetime]) -> list[tuple[datetime, timedelta]]:
    pairs = set()

    for timestamp in timestamps:
        if timestamp.tzinfo is None:
            logger.warning("Naive timestamp encountered, assuming UTC for ts {}", timestamp)
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        offset = timestamp.utcoffset()

        if offset is None:
            logger.warning("Timestamp {} has no utcoffset, skipping", timestamp)
            continue

        utc = timestamp.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
        pairs.add((utc, offset))

    pairs_list = sorted(pairs)
    logger.debug("Computed {} unique (utc, offset) pairs from timestamps", len(pairs_list))
    return pairs_list

def timezones_matching_offset_cached(pairs: Iterable[tuple[datetime, timedelta]]) -> dict[tuple[datetime, timedelta], list[str]]:
    cache: dict[tuple[datetime, timedelta], list[str]] = {}
    all_tz = list(available_timezones())

    logger.debug("Searching among {} available timezones for offset matches", len(all_tz))
    for utc, offset in pairs:
        matches: list[str] = []
        for tz_name in all_tz:
            try:
                tz = ZoneInfo(tz_name)
                local = utc.astimezone(tz)
                if local.utcoffset() == offset:
                    matches.append(tz_name)
            except:
                logger.exception("Zone {} failed during offset check", tz_name)

        cache[(utc, offset)] = matches
        logger.trace("UTC {} offset {} matched {} timezones", utc.isoformat(), offset, len(matches))

    return cache

def infer_countries(user, N: int, use_population_apriori: bool) -> list[dict]:
    logger.info("Starting country inference for top {}", N)

    timestamps = list(user.git_data.timestamps)
    total = len(timestamps)
    if total == 0:
        logger.warning("No timestamps available for user, returning empty list")
        return []

    pairs = unique_utc_pairs(timestamps)
    pair_tz_cache = timezones_matching_offset_cached(pairs)

    timestamp_to_tz_candidates: list[list[str]] = []
    for timestamp in timestamps:
        if timestamp.tzinfo is None:
            logger.warning("Naive timestamp encountered at mapping phase, assuming UTC for ts {}", timestamp)
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        offset = timestamp.utcoffset()
        if offset is None:
            logger.warning("Timestamp {} has no utcoffset, skipping", timestamp)
            timestamp_to_tz_candidates.append([])
            continue

        utc = timestamp.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
        candidates = pair_tz_cache.get((utc, offset), [])
        timestamp_to_tz_candidates.append(candidates)

    logger.debug("Mapped {} timestamps to timezone candidate lists", len(timestamp_to_tz_candidates))

    candidate_countries = set()
    for cand_list in timestamp_to_tz_candidates:
        for tz_name in cand_list:
            countries = TZ_TO_COUNTRY.get(tz_name, [])
            for candidate in countries:
                candidate_countries.add(candidate)

    logger.info("Found {} candidate countries from timezone matches", len(candidate_countries))
    if not candidate_countries:
        logger.warning("No candidate countries discovered, returning empty list")
        return []

    country_stats = {}
    tz_local_hours_cache: dict[str, list[Optional[int]]] = {}

    all_candidate_tzs = set()
    for candidate in candidate_countries:
        tzs = pytz.country_timezones.get(candidate, [])
        for tz in tzs:
            all_candidate_tzs.add(tz)

    logger.debug("Computing local hours for {} timezone candidates", len(all_candidate_tzs))
    for tz_name in all_candidate_tzs:
        hours_for_ts: list[Optional[int]] = []
        try:
            zone = ZoneInfo(tz_name)
        except:
            logger.warning("ZoneInfo cannot build tz {}, filling with None", tz_name)
            tz_local_hours_cache[tz_name] = [None] * len(timestamps)
            continue

        for timestamp in timestamps:
            if timestamp.tzinfo is None:
                ts2 = timestamp.replace(tzinfo=timezone.utc)
            else:
                ts2 = timestamp
            try:
                local = ts2.astimezone(zone)
                hours_for_ts.append(local.hour)
            except:
                hours_for_ts.append(None)

        tz_local_hours_cache[tz_name] = hours_for_ts

    for candidate in candidate_countries:
        tzs = pytz.country_timezones.get(candidate, [])
        if not tzs:
            logger.trace("Country {} has no tz list in pytz, skipping", candidate)
            continue

        matched_count = 0
        wake_hits = 0

        # Wakefullness evaluation
        for idx, candidate_tzs in enumerate(timestamp_to_tz_candidates):
            for tz_name in candidate_tzs:
                countries_for_tz = TZ_TO_COUNTRY.get(tz_name, [])
                if candidate in countries_for_tz:
                    matched_count += 1
                    break

            wake_here = False
            for tz_name in tzs:
                hours = tz_local_hours_cache.get(tz_name)
                if not hours:
                    continue

                hour = hours[idx]
                if hour is None:
                    continue

                if WAKE_START <= hour <= WAKE_END:
                    wake_here = True
                    break

            if wake_here:
                wake_hits += 1

        match_fraction = matched_count / total
        wake_fraction = wake_hits / total

        tz_count = max(1, len(tzs))
        # Here we penalize large multi-timezone countries moderately using sqrt
        tz_penalty = tz_count ** 0.5
        raw_score = (match_fraction * 0.75 + wake_fraction * 0.25) / tz_penalty

        population_prior = 1.0
        if use_population_apriori:
            try:
                pop = CountryInfo(candidate).population()
                population_prior = (float(pop) ** 0.25) if pop and pop > 0 else 1.0
            except:
                logger.trace("Population lookup failed for {}, using prior 1", candidate)
                population_prior = 1.0

        adjusted_score = raw_score * population_prior
        country_stats[candidate] = {
            "match_fraction": match_fraction,
            "wake_fraction": wake_fraction,
            "tz_count": tz_count,
            "raw_score": raw_score,
            "adjusted_score": adjusted_score,
        }

        logger.trace(
            "Country {}, stats match_frac {:.3f}, wake_frac {:.3f}, tz_count {}, raw {:.6f}, adjusted {:.6f}",
            candidate,
            match_fraction,
            wake_fraction,
            tz_count,
            raw_score,
            adjusted_score,
        )

    total_adjusted = sum(s["adjusted_score"] for s in country_stats.values())
    if total_adjusted <= 0:
        logger.warning("All country adjusted scores are zero or negative, falling back to match_fraction ranking")
        # Use match_fraction as score as fallback.
        for candidate, stats in country_stats.items():
            stats["probability"] = stats["match_fraction"]

        _sum = sum(s["probability"] for s in country_stats.values())
        for stats in country_stats.values():
            stats["probability"] = stats["probability"] / _sum if _sum > 0 else 0.0
    else:
        for candidate, stats in country_stats.items():
            stats["probability"] = stats["adjusted_score"] / total_adjusted

    results: list[CountryResult] = []
    for candidate, stats in country_stats.items():
        try:
            info = CountryInfo(candidate).info()
            assert info
            name = info.get("name", candidate)
        except:
            logger.trace("CountryInfo info lookup failed for {}, using code as name", candidate)
            name = candidate
        try:
            flag = countryflag.getflag(name)
        except:
            flag = "🏳"

        results.append(CountryResult(
            code=candidate,
            name=name,
            flag=flag, # pyright: ignore[reportArgumentType]
            score=stats["adjusted_score"] / 100,
            probability=stats["probability"],
            match_fraction=stats["match_fraction"],
            wake_fraction=stats["wake_fraction"],
            tz_count=stats["tz_count"],
        ))

    results.sort(key=lambda r: r.probability, reverse=True)
    out = []

    for result in results[:N]:
        logger.debug(
            "Candidate {} {} prob {:.3%} match {:.2%} wake {:.2%} tzs {}",
            result.code,
            result.name,
            result.probability,
            result.match_fraction,
            result.wake_fraction,
            result.tz_count,
        )

        out.append({
            "code": result.code,
            "name": f"{result.flag}  {result.name}",
            "global_probability": result.probability,
            "local_probability": result.score,
            "match_fraction": result.match_fraction,
            "wake_fraction": result.wake_fraction,
            "tz_count": result.tz_count,
        })

    logger.info("Country inference complete, returning top {}", min(N, len(out)))
    return out
