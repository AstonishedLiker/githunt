from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

import sys

from githunt.CliParser import parser
from githunt.RepositoriesVisitor import visit_repositories
from githunt.GitProviders.GitHub import query_user as github_query_user

from githunt.Analysis.CountryDetectionAlgorithm import infer_countries
from githunt.Analysis.ActivityDetectionAlgorithm import infer_activity

from githunt.Classes.User import User

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

logger.remove(0)

def main() -> None:
    args = parser.parse_args()

    debug_level: str = args.level.upper()
    logger.add(sys.stderr, level=debug_level)
    logger.add(
        args.logs_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level=debug_level
    )

    logger.info("Targetting git host '{}' with username '{}'", args.host, args.username)

    user: Optional[User] = None
    if args.host == "github":
        if not args.personal_access_token:
            logger.warning("")
            logger.warning("Not using a Personal Access Token (PAT)!")
            logger.warning("You can generate one here: https://github.com/settings/personal-access-tokens/new")
            logger.warning("")
            logger.warning("This will potentially reduce the quality of the results")
            logger.warning("You may also get rate-limited by GitHub!")
            logger.warning("")
            logger.warning("For security reasons, please either delete it after use, or make it temporary.")
            logger.warning("")

        blacklisted_orgs_str: str = args.blacklisted_orgs
        blacklisted_orgs = list(map(str.strip, blacklisted_orgs_str.split(",")))

        logger.debug("Blacklisted organizations: {}", blacklisted_orgs)

        user = github_query_user(
            args.username,
            args.scan_forks,
            args.scan_orgs,
            blacklisted_orgs,
            args.personal_access_token,
            args.workers
        )
        if user is None:
            logger.critical("Could not query the GitHub user '{}' (user is None)", args.username)
            exit(1)

        logger.success("Data has been successfully retrieved from the git host")

    assert user
    visit_repositories(user, args.workers, args.alias_based_inference)
    logger.success("Successfully visited repositories")

    logger.info("Captured {} emails:", len(user.git_data.emails))
    for email in user.git_data.emails:
        logger.info("\t- {}", email)

    logger.info("Captured {} aliases:", len(user.git_data.aliases))
    for alias in user.git_data.aliases:
        logger.info("\t- {}", alias)

    logger.info(
        "Captured {} timestamps collected across {} repositories",
        len(user.git_data.timestamps),
        len(user.repositories),
    )

    if args.infer_country:
        inferred_countries = infer_countries(user, args.top_countries, args.use_population_apriori)
        logger.success("Successfully inferred countries")
        logger.info("Inferred countries:")
        for position, country_info in enumerate(inferred_countries):
            logger.info(
                "\t- {}) {} (chance: {:.1f}% locally,  {:.1f}% globally)",
                position + 1,
                country_info["name"],
                country_info["local_probability"] * 100,
                country_info["global_probability"] * 100
            )

    if args.infer_activity:
        ratio_interactions_per_day, average_bounds_per_day = infer_activity(user)
        logger.success("Successfully inferred activity")

        sorted_ratio = {day: ratio_interactions_per_day[day] for day in DAY_ORDER if day in ratio_interactions_per_day}
        sorted_bounds = {day: average_bounds_per_day[day] for day in DAY_ORDER if day in average_bounds_per_day}

        logger.info("Activity repartition:")
        for day, ratio in sorted_ratio.items():
            logger.info("\t- {}: {:.1f}% of activity", day, ratio * 100)

        logger.info("Average active hours:")
        for day, bounds in sorted_bounds.items():
            lower_bound_timedelta = timedelta(seconds=bounds[0])
            upper_bound_timedelta = timedelta(seconds=bounds[1])

            midnight = datetime.min
            lower_bound_time = (midnight + lower_bound_timedelta).time().strftime("%H:%M")
            upper_bound_time = (midnight + upper_bound_timedelta).time().strftime("%H:%M")

            logger.info("\t- {}: from {} to {}", day, lower_bound_time, upper_bound_time)
