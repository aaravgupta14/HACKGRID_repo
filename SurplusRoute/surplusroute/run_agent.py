import argparse

from surplusroute import config
from surplusroute.agent import SurplusRouteAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commodity", default=config.TRACKED[0][0])
    parser.add_argument("--state", default=config.TRACKED[0][1])
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to latest date in cached data")
    args = parser.parse_args()

    agent = SurplusRouteAgent(args.commodity, args.state)
    as_of = args.date or agent.latest_date()
    report = agent.run(as_of)
    path = agent.save_report(report)

    print(f"SurplusRoute glut alerts: {report['commodity']} / {report['state']} as of {report['as_of']}")
    if report["status"] != "ok":
        print("No mandi data reported for this date.")
        return
    summary = report["summary"]
    print(f"Districts tracked: {summary['districts_tracked']} | HIGH: {summary['high_risk']} | "
          f"WATCH: {summary['watch']} | State arrivals vs baseline: {summary['state_arrival_vs_baseline_pct']}%")
    print("-" * 100)
    for alert in report["alerts"]:
        print(f"[{alert['risk_level']:<6}] {alert['verdict']}")
        if alert["risk_level"] != "NORMAL":
            print(f"          Action: {alert['action']}")
            for option in alert["reroute_to"]:
                print(f"          Reroute: {option['district']} at Rs {option['modal_price']:,.0f}/qtl "
                      f"(+Rs {option['price_gap_per_quintal']:,.0f}), risk {option['crash_probability']:.0%}")
    print("-" * 100)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    main()
