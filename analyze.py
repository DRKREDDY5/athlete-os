import pandas as pd

pd.set_option('display.width', 200)

phys = pd.read_csv('physiological_cycles.csv')
work = pd.read_csv('workouts.csv')
sleep = pd.read_csv('sleeps.csv')

def sep(title):
    print("\n" + "="*80)
    print(title)
    print("="*80)

sep("PHYS shape/dtypes")
print(phys.shape)
print(phys.dtypes)

sep("PHYS date range")
phys['Cycle start time'] = pd.to_datetime(phys['Cycle start time'])
print(phys['Cycle start time'].min(), phys['Cycle start time'].max())
print("n_days:", phys['Cycle start time'].dt.date.nunique())

sep("PHYS nulls")
print(phys.isnull().sum())

sep("PHYS duplicates on Cycle start time")
print(phys['Cycle start time'].duplicated().sum())

sep("WORK shape/dtypes")
print(work.shape)
print(work.dtypes)
work['Workout start time'] = pd.to_datetime(work['Workout start time'])
sep("WORK date range")
print(work['Workout start time'].min(), work['Workout start time'].max())

sep("WORK activity counts")
print(work['Activity name'].value_counts())

sep("WORK nulls")
print(work.isnull().sum())

sep("WORK duplicates")
print(work.duplicated().sum())

sep("WORK strain by activity - mean")
print(work.groupby('Activity name')['Activity Strain'].agg(['mean','max','count']).sort_values('mean', ascending=False))

sep("WORK avg HR / cal by activity")
print(work.groupby('Activity name')[['Average HR (bpm)','Energy burned (cal)','Duration (min)']].mean())

sep("WORK duration outliers (>200 min)")
print(work[work['Duration (min)']>200][['Workout start time','Activity name','Duration (min)','Activity Strain']])

sep("WORK weird small values (Duration <5 or Strain 0)")
print(work[(work['Duration (min)']<5)])

sep("SLEEP shape/dtypes")
print(sleep.shape)
print(sleep.dtypes)
sleep['Sleep onset'] = pd.to_datetime(sleep['Sleep onset'])
sep("SLEEP date range")
print(sleep['Sleep onset'].min(), sleep['Sleep onset'].max())

sep("SLEEP nap counts")
print(sleep['Nap'].value_counts(dropna=False))

sep("SLEEP nulls")
print(sleep.isnull().sum())

sep("SLEEP performance stats (naps excluded)")
main_sleep = sleep[sleep['Nap']==False]
print(main_sleep['Sleep performance %'].describe())

sep("SLEEP consistency stats")
print(main_sleep['Sleep consistency %'].describe())

sep("PHYS recovery/hrv/rhr describe")
print(phys[['Recovery score %','Heart rate variability (ms)','Resting heart rate (bpm)','Sleep performance %','Day Strain']].describe())

sep("PHYS rows with missing recovery (likely partial/edge cycles)")
print(phys[phys['Recovery score %'].isnull()][['Cycle start time','Cycle end time','Day Strain','Energy burned (cal)']])

sep("Correlation matrix (numeric, phys)")
cols = ['Recovery score %','Heart rate variability (ms)','Resting heart rate (bpm)','Sleep performance %','Day Strain','Skin temp (celsius)','Blood oxygen %']
print(phys[cols].corr().round(2))

sep("Does yesterday strain correlate with next day recovery?")
p = phys.sort_values('Cycle start time').reset_index(drop=True)
p['next_recovery'] = p['Recovery score %'].shift(-1)
print(p[['Day Strain','next_recovery']].corr())

sep("Sleep performance vs recovery correlation")
print(phys[['Sleep performance %','Recovery score %']].corr())

sep("Workout freq by day of week")
work['dow'] = work['Workout start time'].dt.day_name()
print(work['dow'].value_counts())

sep("Workout freq by hour")
print(work['Workout start time'].dt.hour.value_counts().sort_index())
