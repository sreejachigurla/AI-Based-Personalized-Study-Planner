def generate_plan(df):

    df["priority"] = (100 - df["marks"])

    df = df.sort_values(by="priority", ascending=False)

    plan = []

    for subject in df["subject"]:
        plan.append(f"Study {subject} for 1 hour")

    return plan