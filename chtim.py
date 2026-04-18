from datetime import datetime

# Define work hours
start_time = "01:00:00"    # Start of work shift (9:00 AM)
end_time = "2:00:00"      # End of work shift (5:00 PM)

# Time to check (replace this with any time you want to check, or use datetime.now())
check_time = "01:30:00"    # Example time within work hours

# Convert times to datetime objects
time_format = "%H:%M:%S"
start_dt = datetime.strptime(start_time, time_format)
end_dt = datetime.strptime(end_time, time_format)
check_dt = datetime.strptime(check_time, time_format)

# Check if the time falls within the work hours using `and`
if check_dt >= start_dt and check_dt <= end_dt:
    print(f"{check_time} is within work hours ({start_time} to {end_time}).")
else:
    print(f"{check_time} is outside work hours ({start_time} to {end_time}).")
