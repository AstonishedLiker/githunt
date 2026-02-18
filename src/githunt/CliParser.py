import argparse

parser = argparse.ArgumentParser(
	description="The ultimate git OSINT tool"
)

# Core
parser.add_argument(
	"--proxy",
	help="Optional proxy (http://127.0.0.1:8080)"
)

parser.add_argument(
	"--host",
	choices=["github"],
	required=True,
	help="Git host"
)

parser.add_argument(
	"-u",
	"--username",
	required=True,
	help="Target username"
)

parser.add_argument(
	"--pat",
    dest="personal_access_token",
	help="GitHub Personal Access Token (PAT) to improve results"
)

parser.add_argument(
	"--logs-path",
	help="Logs location",
    default="./githunt.log"
)

parser.add_argument(
	"--level",
	help="Minimum log level that will get outputted",
    choices=["trace", "debug", "info", "warning", "error", "critical"],
    default="info"
)

parser.add_argument(
	"--top-countries",
	help="The number of countries to show",
    type=int,
    default=5
)

parser.add_argument(
	"--workers",
	help="Workers count for visiting repository",
    type=int,
    default=7
)

# Feature toggles
parser.add_argument(
	"--no-country",
	dest="country",
	action="store_false",
	help="Disable country inference"
)

parser.add_argument(
	"--no-alias-based-inference",
	dest="alias_based_inference",
	action="store_false",
	help="Disable alias-based infering for finding emails"
)

parser.add_argument(
	"--no-scan-orgs",
	dest="scan_orgs",
	action="store_false",
	help="Disable linked organizations scanning"
)

parser.add_argument(
	"--no-cross-check",
	dest="cross_check",
	action="store_false",
	help="Disable metadata cross-checking"
)

parser.add_argument(
	"--no-active-hours",
	action="store_false",
	help="Disables active hours inference"
)

parser.add_argument(
	"--scan-forks",
	action="store_true",
	help="Include forked repositories in analysis"
)

parser.add_argument(
	"--communities",
	action="store_true",
	help="Run Louvain community detection"
)

parser.add_argument(
	"--bot-detection",
	action="store_true",
	help="Detect automated/spam/follow-all behavior"
)

parser.set_defaults(
	country=True,
	cross_check=True
)
