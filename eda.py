# %% Imports
import pandas as pd
from IPython.display import display

# %% Load dataset
df = pd.read_csv("porto/porto.csv")

# %%

display(df.describe())
display(df.head())

# %% [markdown]
# # Test
# Test
