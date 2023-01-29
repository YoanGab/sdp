from typing import TypedDict

from entities import Job, Employee


class ProblemData(TypedDict):
    horizon: int
    qualifications: list[str]
    staff: list[Employee]
    jobs: list[Job]
