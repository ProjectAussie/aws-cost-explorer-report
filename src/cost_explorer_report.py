#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Cost Explorer Report

A script, for local or lambda use, to generate CostExplorer excel graphs
"""

from __future__ import print_function

import datetime
import logging
import os
import sys

# For email
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

import boto3
import pandas as pd

# for rds access
import rds_access

# For date
from dateutil.relativedelta import relativedelta

# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))


# GLOBALS
SES_REGION = os.getenv("SES_REGION", "us-east-1")
ACCOUNT_LABEL = os.getenv("ACCOUNT_LABEL", "Email")

CURRENT_DAY = os.getenv("CURRENT_DAY", "false")
if CURRENT_DAY == "true":
    CURRENT_DAY = True
else:
    CURRENT_DAY = False

LAST_MONTH_ONLY = os.getenv("LAST_MONTH_ONLY")
TRAILING_DAYS = os.getenv("TRAILING_DAYS", "7")

# Default exclude support, as for Enterprise Support
# as support billing is finalised later in month so skews trends
INC_SUPPORT = os.getenv("INC_SUPPORT", "true")
if INC_SUPPORT == "true":
    INC_SUPPORT = True
else:
    INC_SUPPORT = False

TAG_VALUE_FILTER = os.getenv("TAG_VALUE_FILTER", "*")
TAG_KEY = os.getenv("TAG_KEY")


class CostExplorer:
    """Retrieves BillingInfo checks from CostExplorer API
    >>> costexplorer = CostExplorer()
    >>> costexplorer.add_report(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    >>> costexplorer.generate_excel()
    """

    def __init__(self, report_name="cost_explorer_report.xlsx"):
        # Array of reports ready to be output to Excel.
        self.reports = []
        self.report_name = report_name
        self.client = boto3.client("ce", region_name="us-east-1")
        self.end = datetime.date.today() - datetime.timedelta(days=1)
        self.riend = datetime.date.today()
        if CURRENT_DAY:
            self.end = self.riend

        if TRAILING_DAYS:
            # generally only want like 7 days worth of dat
            self.start = datetime.date.today() - relativedelta(days=+int(TRAILING_DAYS))
        elif LAST_MONTH_ONLY:
            self.start = (datetime.date.today() - relativedelta(months=+1)).replace(
                day=1
            )  # 1st day of month a month ago
        else:
            # Default is last 12 months
            self.start = (datetime.date.today() - relativedelta(months=+12)).replace(
                day=1
            )  # 1st day of month 12 months ago

        self.ristart = (datetime.date.today() - relativedelta(months=+11)).replace(
            day=1
        )  # 1st day of month 11 months ago
        self.sixmonth = (datetime.date.today() - relativedelta(months=+6)).replace(
            day=1
        )  # 1st day of month 6 months ago, so RI util has savings values
        self.accounts = self.get_accounts()

    def get_accounts(self):
        accounts = {}
        client = boto3.client("organizations", region_name="us-east-1")
        try:
            paginator = client.get_paginator("list_accounts")
            response_iterator = paginator.paginate()
            for response in response_iterator:
                for acc in response["Accounts"]:
                    accounts[acc["Id"]] = acc
        except client.exceptions.AWSOrganizationsNotInUseException:
            logging.exception("Getting Account names failed")
            accounts = {}

        return accounts

    def add_ri_report(
        self,
        Name="RICoverage",
        Savings=False,
        PaymentOption="PARTIAL_UPFRONT",
        Service="Amazon Elastic Compute Cloud - Compute",
        Granularity="DAILY",
    ):  # Call with Savings True to get Utilization report in dollar savings
        type = "chart"  # other option table
        if Name == "RICoverage":
            results = []
            response = self.client.get_reservation_coverage(
                TimePeriod={
                    "Start": self.ristart.isoformat(),
                    "End": self.riend.isoformat(),
                },
                Granularity=Granularity,
            )
            results.extend(response["CoveragesByTime"])
            while "nextToken" in response:
                nextToken = response["nextToken"]
                response = self.client.get_reservation_coverage(
                    TimePeriod={
                        "Start": self.ristart.isoformat(),
                        "End": self.riend.isoformat(),
                    },
                    Granularity=Granularity,
                    NextPageToken=nextToken,
                )
                results.extend(response["CoveragesByTime"])
                if "nextToken" in response:
                    nextToken = response["nextToken"]
                else:
                    nextToken = False

            rows = []
            for v in results:
                row = {"date": v["TimePeriod"]["Start"]}
                row.update(
                    {
                        "Coverage%": float(
                            v["Total"]["CoverageHours"]["CoverageHoursPercentage"]
                        )
                    }
                )
                rows.append(row)

            df = pd.DataFrame(rows)
            df.set_index("date", inplace=True)
            df = df.fillna(0.0)
            df = df.T
        elif Name in ["RIUtilization", "RIUtilizationSavings"]:
            # Only Six month to support savings
            results = []
            response = self.client.get_reservation_utilization(
                TimePeriod={
                    "Start": self.sixmonth.isoformat(),
                    "End": self.riend.isoformat(),
                },
                Granularity=Granularity,
            )
            results.extend(response["UtilizationsByTime"])
            while "nextToken" in response:
                nextToken = response["nextToken"]
                response = self.client.get_reservation_utilization(
                    TimePeriod={
                        "Start": self.sixmonth.isoformat(),
                        "End": self.riend.isoformat(),
                    },
                    Granularity=Granularity,
                    NextPageToken=nextToken,
                )
                results.extend(response["UtilizationsByTime"])
                if "nextToken" in response:
                    nextToken = response["nextToken"]
                else:
                    nextToken = False

            rows = []
            if results:
                for v in results:
                    row = {"date": v["TimePeriod"]["Start"]}
                    if Savings:
                        row.update({"Savings$": float(v["Total"]["NetRISavings"])})
                    else:
                        row.update(
                            {"Utilization%": float(v["Total"]["UtilizationPercentage"])}
                        )
                    rows.append(row)

                df = pd.DataFrame(rows)
                df.set_index("date", inplace=True)
                df = df.fillna(0.0)
                df = df.T
                type = "chart"
            else:
                df = pd.DataFrame(rows)
                type = "table"  # Dont try chart empty result
        elif Name == "RIRecommendation":
            results = []
            response = self.client.get_reservation_purchase_recommendation(
                # AccountId='string', May use for Linked view
                LookbackPeriodInDays="SIXTY_DAYS",
                TermInYears="ONE_YEAR",
                PaymentOption=PaymentOption,
                Service=Service,
            )
            results.extend(response["Recommendations"])
            while "nextToken" in response:
                nextToken = response["nextToken"]
                response = self.client.get_reservation_purchase_recommendation(
                    # AccountId='string', May use for Linked view
                    LookbackPeriodInDays="SIXTY_DAYS",
                    TermInYears="ONE_YEAR",
                    PaymentOption=PaymentOption,
                    Service=Service,
                    NextPageToken=nextToken,
                )
                results.extend(response["Recommendations"])
                if "nextToken" in response:
                    nextToken = response["nextToken"]
                else:
                    nextToken = False

            rows = []
            for i in results:
                for v in i["RecommendationDetails"]:
                    row = v["InstanceDetails"][list(v["InstanceDetails"].keys())[0]]
                    row["Recommended"] = v["RecommendedNumberOfInstancesToPurchase"]
                    row["Minimum"] = v["MinimumNumberOfInstancesUsedPerHour"]
                    row["Maximum"] = v["MaximumNumberOfInstancesUsedPerHour"]
                    row["Savings"] = v["EstimatedMonthlySavingsAmount"]
                    row["OnDemand"] = v["EstimatedMonthlyOnDemandCost"]
                    row["BreakEvenIn"] = v["EstimatedBreakEvenInMonths"]
                    row["UpfrontCost"] = v["UpfrontCost"]
                    row["MonthlyCost"] = v["RecurringStandardMonthlyCost"]
                    rows.append(row)

            df = pd.DataFrame(rows)
            df = df.fillna(0.0)
            type = "table"  # Dont try chart this
        self.reports.append({"Name": Name, "Data": df, "Type": type})

    def add_linked_reports(self, Name="RI_{}", PaymentOption="PARTIAL_UPFRONT"):
        pass

    def add_report(
        self,
        Name="Default",
        GroupBy=None,
        Style="Total",
        Granularity="DAILY",
        NoCredits=True,
        CreditsOnly=False,
        RefundOnly=False,
        UpfrontOnly=False,
        IncSupport=False,
    ):
        type = "chart"  # other option table
        results = []
        if not NoCredits:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    "Start": self.start.isoformat(),
                    "End": self.end.isoformat(),
                },
                Granularity=Granularity,
                Metrics=[
                    "UnblendedCost",
                ],
                GroupBy=GroupBy,
            )
        else:
            Filter = {"And": []}

            Dimensions = {
                "Not": {
                    "Dimensions": {
                        "Key": "RECORD_TYPE",
                        "Values": ["Credit", "Refund", "Upfront", "Support"],
                    }
                }
            }
            if (
                INC_SUPPORT or IncSupport
            ):  # If global set for including support, we dont exclude it
                Dimensions = {
                    "Not": {
                        "Dimensions": {
                            "Key": "RECORD_TYPE",
                            "Values": ["Credit", "Refund", "Upfront"],
                        }
                    }
                }
            if CreditsOnly:
                Dimensions = {
                    "Dimensions": {
                        "Key": "RECORD_TYPE",
                        "Values": [
                            "Credit",
                        ],
                    }
                }
            if RefundOnly:
                Dimensions = {
                    "Dimensions": {
                        "Key": "RECORD_TYPE",
                        "Values": [
                            "Refund",
                        ],
                    }
                }
            if UpfrontOnly:
                Dimensions = {
                    "Dimensions": {
                        "Key": "RECORD_TYPE",
                        "Values": [
                            "Upfront",
                        ],
                    }
                }

            tagValues = None
            if TAG_KEY:
                tagValues = self.client.get_tags(
                    SearchString=TAG_VALUE_FILTER,
                    TimePeriod={
                        "Start": self.start.isoformat(),
                        "End": datetime.date.today().isoformat(),
                    },
                    TagKey=TAG_KEY,
                )

            if tagValues:
                Filter["And"].append(Dimensions)
                if len(tagValues["Tags"]) > 0:
                    Tags = {"Tags": {"Key": TAG_KEY, "Values": tagValues["Tags"]}}
                    Filter["And"].append(Tags)
            else:
                Filter = Dimensions.copy()

            response = self.client.get_cost_and_usage(
                TimePeriod={
                    "Start": self.start.isoformat(),
                    "End": self.end.isoformat(),
                },
                Granularity=Granularity,
                Metrics=[
                    "UnblendedCost",
                ],
                GroupBy=GroupBy,
                Filter=Filter,
            )

        if response:
            results.extend(response["ResultsByTime"])

            while "nextToken" in response:
                nextToken = response["nextToken"]
                response = self.client.get_cost_and_usage(
                    TimePeriod={
                        "Start": self.start.isoformat(),
                        "End": self.end.isoformat(),
                    },
                    Granularity=Granularity,
                    Metrics=[
                        "UnblendedCost",
                    ],
                    GroupBy=GroupBy,
                    NextPageToken=nextToken,
                )

                results.extend(response["ResultsByTime"])
                if "nextToken" in response:
                    nextToken = response["nextToken"]
                else:
                    nextToken = False
        rows = []
        sort = ""
        for v in results:
            row = {"date": v["TimePeriod"]["Start"]}
            sort = v["TimePeriod"]["Start"]
            for i in v["Groups"]:
                key = i["Keys"][0]
                if key in self.accounts:
                    key = self.accounts[key][ACCOUNT_LABEL]
                row.update({key: float(i["Metrics"]["UnblendedCost"]["Amount"])})
            if not v["Groups"]:
                row.update({"Total": float(v["Total"]["UnblendedCost"]["Amount"])})
            rows.append(row)

        df = pd.DataFrame(rows)
        df.set_index("date", inplace=True)
        df = df.fillna(0.0)

        if Style == "Change":
            dfc = df.copy()
            lastindex = None
            for index, row in df.iterrows():
                if lastindex:
                    for i in row.index:
                        try:
                            df.at[index, i] = dfc.at[index, i] - dfc.at[lastindex, i]
                        except:
                            logging.exception("Error")
                            df.at[index, i] = 0
                lastindex = index

        # before transposing, rows are dates and columns are services
        df = df.T
        df = df.sort_values(sort, ascending=False)
        df["total"] = df.sum(axis=1)
        df = df.sort_values("total", ascending=False)  # sort by total spend on services
        df = df.iloc[:10, :]  # only keep top 10?
        self.reports.append({"Name": Name, "Data": df, "Type": type})

    def add_per_dog_report(self):
        reports = [_report for _report in self.reports if _report["Name"] == "Services"]
        if reports and len(reports) == 1:
            report = reports[0]
        else:
            raise ValueError("Please run the Services report first")

        df = report["Data"]
        n_dogs_by_date = rds_access.get_dogs_per_day()
        df = n_dogs_by_date.join(df.T, how="inner")

        def cost_per_dog(col):
            if col.name != "n_dogs":
                return col / df["n_dogs"]
            else:
                return col

        df = df.apply(cost_per_dog, axis=0).T
        self.reports.append({"Name": "ServicesPerDog", "Data": df, "Type": "chart"})

    def generate_excel(self):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        os.chdir("/tmp")
        writer = pd.ExcelWriter(self.report_name, engine="xlsxwriter")
        workbook = writer.book
        for report in self.reports:
            print(report["Name"], report["Type"])
            report["Data"].to_excel(writer, sheet_name=report["Name"])
            worksheet = writer.sheets[report["Name"]]
            if report["Type"] == "chart":

                # Create a chart object.
                chart = workbook.add_chart({"type": "column", "subtype": "stacked"})
                df = report["Data"]

                if "PerDog" in report["Name"]:
                    row_start = 2
                else:
                    row_start = 1

                chartend = df.shape[1]
                if CURRENT_DAY:
                    chartend = df.shape[1]
                for row_num in range(row_start, len(df) + 1):
                    chart.add_series(
                        {
                            "name": [report["Name"], row_num, 0],
                            "categories": [report["Name"], 0, 1, 0, chartend],
                            "values": [report["Name"], row_num, 1, row_num, chartend],
                        }
                    )
                chart.set_y_axis({"label_position": "low"})
                chart.set_x_axis({"label_position": "low"})
                worksheet.insert_chart("O2", chart, {"x_scale": 2.0, "y_scale": 2.0})
        writer.save()

    def send_s3(self):
        # Time to deliver the file to S3
        s3_bucket = os.environ.get("S3_BUCKET")
        if s3_bucket:
            print(f"Sending to s3 {s3_bucket}...")
            s3 = boto3.client("s3")
            s3.upload_file(
                self.report_name,
                s3_bucket,
                self.report_name,
            )

    def send_email(self):
        ses_send = os.environ.get("SES_SEND")
        ses_from = os.environ.get("SES_FROM")
        if ses_send and ses_from:
            # Email logic
            print(f"Sending email from {ses_from} to {ses_send}")
            msg = MIMEMultipart()
            msg["From"] = ses_from
            msg["To"] = COMMASPACE.join(ses_send.split(","))
            msg["Date"] = formatdate(localtime=True)
            msg["Subject"] = "Cost Explorer Report"
            text = "Find your Cost Explorer report attached\n\n"
            msg.attach(MIMEText(text))
            with open(self.report_name, "rb") as file:
                part = MIMEApplication(file.read(), Name="cost_explorer_report.xlsx")
            part["Content-Disposition"] = 'attachment; filename="%s"' % self.report_name
            msg.attach(part)
            # SES Sending
            ses = boto3.client("ses", region_name=SES_REGION)
            result = ses.send_raw_email(
                Source=msg["From"],
                Destinations=ses_send.split(","),
                RawMessage={"Data": msg.as_string()},
            )
