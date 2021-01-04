import csv
import datetime
import os
import sys

import boto3
import pandas as pd

BUCKET = os.getenv("AWS_PROCESSED_BUCKET")
if BUCKET is None:
    sys.exit("No bucket info is provided (via the AWS_PROCESSED_BUCKET env var)")

df = pd.read_csv(f"s3://{BUCKET}/latest.csv")
df = df.set_index(["archive"])


def load_training_data(archive, df):
    path = df.at[archive, "path"]
    data = pd.read_csv(f"s3://{BUCKET}/{path}", low_memory=False)
    return data[data["group"] == "training"]


output = [["Metric", "Value"]]

patient_clean = load_training_data("patient_clean", df)
ct = load_training_data("ct", df)
mri = load_training_data("mri", df)
xray = load_training_data("xray", df)


patients_with_images = (
    set(ct["Pseudonym"]) | set(mri["Pseudonym"]) | set(xray["Pseudonym"])
)
patients_training_positive = set(
    patient_clean[patient_clean["filename_covid_status"]]["Pseudonym"]
)
patients_training_negative = set(
    patient_clean[~patient_clean["filename_covid_status"]]["Pseudonym"]
)

count_patients_training_positive_images = len(
    patients_training_positive & patients_with_images
)
count_patients_training_negative_images = len(
    patients_training_negative & patients_with_images
)

date_cutoff = datetime.datetime.now() - datetime.timedelta(30)
recent_patients = sum(
    pd.to_datetime(patient_clean["filename_earliest_date"]) >= date_cutoff
)

output += [
    [
        "**Total number of patients with images**",
        f"**{count_patients_training_positive_images+count_patients_training_negative_images:,.0f}**",
    ],
    [
        "Positive patients with images",
        f"{count_patients_training_positive_images:,.0f}",
    ],
    [
        "Negative patients with images",
        f"{count_patients_training_negative_images:,.0f}",
    ],
    ["New patients added in the last 30 days", f"{recent_patients:,.0f}"],
    ["", ""],
]

ct_studies = ct["StudyInstanceUID"].nunique()
mri_studies = mri["StudyInstanceUID"].nunique()
xray_studies = xray["StudyInstanceUID"].nunique()

img_counts = {
    "CT image studies": ct_studies,
    "MRI image studies": mri_studies,
    "X-ray image studies": xray_studies,
}

sorted_img_counts = list(
    map(
        lambda item: [item[0], f"{item[1]:,.0f}"],
        sorted(
            [[item, img_counts[item]] for item in img_counts],
            key=lambda item: item[1],
            reverse=True,
        ),
    )
)

output += [
    [
        "**Total number of image studies**",
        f"**{ct_studies+mri_studies+xray_studies:,.0f}**",
    ]
]
output += sorted_img_counts
output += [["", ""]]

nhs_trusts = patient_clean["SubmittingCentre"].nunique()
output += [
    ["**Submitting centres (e.g. NHS trusts)**", f"**{nhs_trusts:,.0f}**"],
]


with open("stats.csv", "w") as csvfile:
    statswriter = csv.writer(
        csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    statswriter.writerows(output)

with open("stats_date.txt", "w") as fragment:
    now = datetime.datetime.now()
    fragment.write(
        f"*This information was last updated on {now.strftime('%-d %B %Y')}.*"
    )