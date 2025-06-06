import pandas as pd
import re

# Load the ADR.csv file
adr_df = pd.read_csv("ADR.csv")

# Select relevant columns from ADR.csv
adr_df = adr_df[["Name", "Team", "ADP", "FantasyPros", "ESPN", "Pos"]]

# Filter ADR data for players with an ADP rank of 311 or less
adr_df = adr_df[adr_df["ADP"] <= 311]

# Load the ECR.csv file
ecr_df = pd.read_csv("ECR.csv")

# Rename columns to match the desired output
ecr_df = ecr_df.rename(
    columns={
        "RK": "ECR",
        "TIERS": "FantasyPros Tier",
        "PLAYER NAME": "Name",
        "ECR VS. ADP": "ECR vs ADP",
    }
)

# Select relevant columns from ECR.csv
ecr_df = ecr_df[["Name", "FantasyPros Tier", "ECR", "ECR vs ADP"]]


# Define a function to clean player names by removing suffixes like "Jr.", "Sr.", "II", "III"
def clean_name(name):
    suffixes = ["Jr.", "Sr.", "II", "III", "IV", "V"]
    # Use regex to remove suffixes if they appear at the end of the name
    name = re.sub(r"\s+(?:" + "|".join(suffixes) + r")$", "", name)
    return name


# Apply the cleaning function to both dataframes
adr_df["Name"] = adr_df["Name"].apply(clean_name)
ecr_df["Name"] = ecr_df["Name"].apply(clean_name)

# Merge the two DataFrames on the 'Name' column, only keep players in both lists
combined_df = pd.merge(adr_df, ecr_df, on="Name", how="inner")


# Assign Depth based on position and order within the team
def assign_depth(group):
    depth_chart = {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "DST": 1}

    def get_depth(position):
        if position in depth_chart:
            depth = f"{position}{depth_chart[position]}"
            depth_chart[position] += 1
            return depth
        return ""

    group["Depth"] = group["Pos"].apply(get_depth)
    return group


# Apply depth assignment function to each team group
combined_df = combined_df.groupby("Team").apply(assign_depth)

# Save the combined DataFrame to a new CSV file with Depth column
combined_df.to_csv("combined_with_depth.csv", index=False)

print("Combined CSV with Depth created successfully!")
