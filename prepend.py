#!/usr/bin/env python
import os
from shutil import copyfile

## Process the schedule document
names = []
days = []

with open("./metadata/schedule.csv", "r") as file_schedule:
    ## Dump the header
    file_schedule.readline()
    ## Process each line
    for i, line in enumerate(file_schedule):
        name, day = line.split(",")
        names.append(name)
        days.append(int(day))

## Copy the exercises
dir_base = os.path.dirname(__file__)

# Assignment exercises
for i in range(len(names)):
    source = os.path.join(dir_base, "exercises", names[i] + "-assignment.ipynb")
    target = os.path.join(
        dir_base,
        "exercises_assignment",
        "d{0:02d}-".format(days[i]) + \
        names[i] + \
        "-assignment.ipynb"
    )

    copyfile(source, target)

# Solutions (book)
for i in range(len(names)):
    source = os.path.join(dir_base, "exercises", names[i] + "-solution.ipynb")
    target = os.path.join(
        dir_base,
        "exercises_solution",
        "d{0:02d}-".format(days[i]) + \
        names[i] + \
        "-solution.ipynb"
    )

    copyfile(source, target)
