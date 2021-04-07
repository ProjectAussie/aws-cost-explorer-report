import os

from cost_explorer_report import CostExplorer


def main_handler(event=None, context=None):
    print("In main_handler")
    costexplorer = CostExplorer()
    # Default addReport has filter to remove Support / Credits / Refunds / UpfrontRI
    # Overall Billing Reports
    costexplorer.add_report(Name="Total", GroupBy=[], Style="Total", IncSupport=True)
    costexplorer.add_report(Name="TotalChange", GroupBy=[], Style="Change")
    costexplorer.add_report(
       Name="TotalInclCredits",
       GroupBy=[],
       Style="Total",
       NoCredits=False,
       IncSupport=True,
    )
    costexplorer.add_report(
        Name="Services",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        Style="Total",
        IncSupport=True,
    )
    costexplorer.add_per_dog_report()
    costexplorer.add_report(
        Name="ServicesChange",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        Style="Change",
    )
    costexplorer.add_report(
        Name="Regions", GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}], Style="Total"
    )
    costexplorer.generate_excel()
    if os.environ.get("S3_BUCKET"):
        costexplorer.send_s3()
    if os.environ.get("SES_SEND"):
        costexplorer.send_email()
    print("Report generated")


if __name__ == "__main__":
    main_handler()
