from cost_explorer_report import CostExplorer
import os


def main_handler(event=None, context=None):
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
        Name="TotalInclCreditsChange", GroupBy=[], Style="Change", NoCredits=False
    )
    costexplorer.add_report(Name="Credits", GroupBy=[], Style="Total", CreditsOnly=True)
    costexplorer.add_report(Name="Refunds", GroupBy=[], Style="Total", RefundOnly=True)
    costexplorer.add_report(
        Name="RIUpfront", GroupBy=[], Style="Total", UpfrontOnly=True
    )
    # GroupBy Reports
    costexplorer.add_report(
        Name="Services",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        Style="Total",
        IncSupport=True,
    )
    costexplorer.add_report(
        Name="ServicesChange",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        Style="Change",
    )
    costexplorer.add_report(
        Name="Accounts",
        GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        Style="Total",
    )
    costexplorer.add_report(
        Name="AccountsChange",
        GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        Style="Change",
    )
    costexplorer.add_report(
        Name="Regions", GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}], Style="Total"
    )
    costexplorer.add_report(
        Name="RegionsChange",
        GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}],
        Style="Change",
    )
    if os.environ.get(
        "COST_TAGS"
    ):  # Support for multiple/different Cost Allocation tags
        for tagkey in os.environ.get("COST_TAGS").split(","):
            tabname = tagkey.replace(
                ":", "."
            )  # Remove special chars from Excel tabname
            costexplorer.add_report(
                Name="{}".format(tabname)[:31],
                GroupBy=[{"Type": "TAG", "Key": tagkey}],
                Style="Total",
            )
            costexplorer.add_report(
                Name="Change-{}".format(tabname)[:31],
                GroupBy=[{"Type": "TAG", "Key": tagkey}],
                Style="Change",
            )
    # RI Reports
    # costexplorer.addRiReport(Name="RICoverage")
    # costexplorer.addRiReport(Name="RIUtilization")
    # costexplorer.addRiReport(Name="RIUtilizationSavings", Savings=True)
    # costexplorer.addRiReport(Name="RIRecommendation") #Service supported value(s): Amazon Elastic Compute Cloud - Compute, Amazon Relational Database Service
    costexplorer.generate_excel()
    if os.environ.get("S3_BUCKET"):
        costexplorer.send_s3()
    if os.environ.get("SES_SEND"):
        costexplorer.send_email()
    print("Report generated")


if __name__ == "__main__":
    main_handler()
