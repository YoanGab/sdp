import json
from typing import TypedDict

import gurobipy

from entities import Employee, Job


# Create a typed dict to store all data of the problem
class ProblemData(TypedDict):
    horizon: int
    qualifications: list[str]
    staff: list[Employee]
    jobs: list[Job]


def get_data(size: str) -> ProblemData:
    if size == "small":
        file: str = "data/toy_instance.json"
    elif size == "medium":
        file: str = "data/medium_instance.json"
    elif size == "large":
        file: str = "data/large_instance.json"
    else:
        raise ValueError(f"Unknown size {size}")

    with open(file) as f:
        data: dict = json.load(f)

    data["staff"] = [
        Employee(
            name=employee["name"],
            qualifications=employee["qualifications"],
            vacations=employee["vacations"],
        )
        for index, employee in enumerate(data["staff"])
    ]

    data["jobs"] = [
        Job(
            name=job["name"],
            gain=job["gain"],
            due_date=job["due_date"],
            daily_penalty=job["daily_penalty"],
            working_days_per_qualification=job["working_days_per_qualification"],
        )
        for index, job in enumerate(data["jobs"])
    ]

    return data


def get_profit(project: Job, end_date: int) -> int:
    if project.due_date >= end_date:
        return project.gain
    return max(project.gain - project.daily_penalty * (end_date - project.due_date), 0)


def solve_problem(
    data: ProblemData,
) -> any:
    profits_jobs: dict = {
        (job_index, day): get_profit(job, day)
        for job_index, job in enumerate(data["jobs"])
        for day in range(data["horizon"])
    }
    model: gurobipy.Model = gurobipy.Model()

    # Create variables
    # X[e, j, d] = 1 if employee e works on job j on day d
    # Y[e, j, q] = 1 if employee e is assigned to job j for qualification q
    # Z[j, d] = 1 if job j is finished on day d

    X: gurobipy.tupledict = model.addVars(
        len(data["staff"]),
        len(data["jobs"]),
        data["horizon"],
        vtype=gurobipy.GRB.BINARY,
        name="X",
    )

    Y: gurobipy.tupledict = model.addVars(
        len(data["staff"]),
        len(data["jobs"]),
        len(data["qualifications"]),
        vtype=gurobipy.GRB.BINARY,
        name="Y",
    )

    Z: gurobipy.tupledict = model.addVars(
        len(data["jobs"]),
        data["horizon"],
        vtype=gurobipy.GRB.BINARY,
        name="Z",
    )

    model.update()

    model.setObjective(
        gurobipy.quicksum(
            profits_jobs[job_index, day] * Z[job_index, day]
            for job_index, _ in enumerate(data["jobs"])
            for day in range(data["horizon"])
        ),
        gurobipy.GRB.MAXIMIZE,
    )

    # Add constraints

    # Constraint 1 : A project must be realized in a number of consecutive days
    # TODO

    # Constraint 2 : An employee can only be assigned to a project qualification if he has this qualification
    model.addConstrs(
        (
            Y[employee_index, job_index, qualification_index] == 0
            for employee_index, employee in enumerate(data["staff"])
            for job_index, _ in enumerate(data["jobs"])
            for qualification_index, qualification in enumerate(data["qualifications"])
            if qualification not in employee.qualifications
        ),
        name="Need to have qualification to work on a job",
    )

    # Constraint 3: An employee can only be assigned to one qualification for a job
    # Number of qualifications per employee per job <= 1
    model.addConstrs(
        (
            gurobipy.quicksum(
                Y[employee_index, job_index, qualification_index]
                for qualification_index, _ in enumerate(data["qualifications"])
            )
            <= 1
            for employee_index, _ in enumerate(data["staff"])
            for job_index, _ in enumerate(data["jobs"])
        ),
        name="One qualification per employee per job",
    )

    # Constraint 4 : An employee can only be assigned to one project per day
    # Number of jobs per employee per day <= 1
    model.addConstrs(
        (
            gurobipy.quicksum(
                X[employee_index, job_index, day]
                for job_index, _ in enumerate(data["jobs"])
            )
            <= 1
            for employee_index, _ in enumerate(data["staff"])
            for day in range(data["horizon"])
        ),
        name="One job per employee per day",
    )

    # Constraint 5: An employee must not work on a day of vacation
    # X[e, j, d] = 0 if d in employee e vacations
    model.addConstrs(
        (
            X[employee_index, job_index, day] == 0
            for employee_index, employee in enumerate(data["staff"])
            for job_index, _ in enumerate(data["jobs"])
            for day in employee.vacations
        ),
        name="No work on vacation",
    )

    # Constraint 6: A project is realized when each qualification has been staffed the right number of days
    # Z[j, d] = 1 if for all days d' in 0..d, sum(Y[e, j, q] * X[e, j, d']) == working_days_per_qualification[q] for all q
    # TODO
    # model.addConstrs(
    #     (
    #         Z[job_index, day]
    #         == (
    #             gurobipy.quicksum(
    #                 Y[employee_index, job_index, qualification_index]
    #                 * X[employee_index, job_index, day_2]
    #                 for employee_index, _ in enumerate(data["staff"])
    #                 for day_2 in range(day + 1)
    #             )
    #             == data["jobs"][job_index].working_days_per_qualification.get(
    #                 qualification, 0
    #             )
    #             for qualification_index, qualification in enumerate(
    #                 data["qualifications"]
    #             )
    #         )
    #         for job_index, job in enumerate(data["jobs"])
    #         for day in range(data["horizon"])
    #     ),
    #     name="Project is realized when each qualification has been staffed the right number of days",
    # )

    # Constraint 7: A project can only be realized once
    model.addConstrs(
        (
            gurobipy.quicksum(Z[job_index, day] for day in range(data["horizon"])) == 1
            for job_index, _ in enumerate(data["jobs"])
        ),
        name="A job can only be realized once",
    )

    # Constraint 8: The problem takes place over a given period of time
    # Already solved?

    model.optimize()
    if model.Status == gurobipy.GRB.OPTIMAL:
        print(model.objVal)
        return model.objVal


def main() -> None:
    data: ProblemData = get_data("small")
    print(type(data))
    print(data)

    solution = solve_problem(data)
    print(f"Solution: {solution}")


if __name__ == "__main__":
    main()
