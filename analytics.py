from db import marks
import pandas as pd

def get_student_data(username):
    data = list(marks.find({"username": username}))
    return pd.DataFrame(data)