from nselib import indices

# Fetch live performance data for all indices
live_data = indices.live_index_performances()

# View the data
print(live_data.head())