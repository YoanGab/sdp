import json

import gurobipy


class Employee:
    def __init__(
        self, index: int, name: str, qualifications: list[str], vacations: list[int]
    ):
        self.index = index
        self.name = name
        self.qualifications = qualifications
        self.vacations = vacations


class Project:
    def __init__(
        self,
        index: int,
        name: str,
        gain: int,
        due_date: int,
        daily_penalty: int,
        working_days_per_qualification: dict[str, int],
    ):
        self.index = index
        self.name = name
        self.gain = gain
        self.due_date = due_date
        self.daily_penalty = daily_penalty
        self.working_days_per_qualification = working_days_per_qualification


def get_data(size: str) -> dict:
    if size == "small":
        file: str = "data/toy_instance.json"
    elif size == "medium":
        file: str = "data/medium_instance.json"
    elif size == "large":
        file: str = "data/large_instance.json"
    else:
        raise ValueError(f"Unknown size {size}")

    with open(file) as f:
        return json.load(f)


def main() -> None:
    data: dict = get_data("small")
    horizon: int = data["horizon"]
    qualifications: list[str] = data["qualifications"]
    staff: list[Employee] = [
        Employee(
            index=index,
            name=employee["name"],
            qualifications=employee["qualifications"],
            vacations=employee["vacations"],
        )
        for index, employee in enumerate(data["staff"])
    ]
    jobs: list[Project] = [
        Project(
            index=index,
            name=job["name"],
            gain=job["gain"],
            due_date=job["due_date"],
            daily_penalty=job["daily_penalty"],
            working_days_per_qualification=job["working_days_per_qualification"],
        )
        for index, job in enumerate(data["jobs"])
    ]
    print(
        f"Horizon: {horizon}, qualifications: {qualifications}, staff: {staff}, projects: {jobs}"
    )

    solution = solve_problem(horizon, qualifications, staff, jobs)
    print(f"Solution: {solution}")


def get_penalty(project: Project, end_date: int) -> int:
    if project.due_date >= end_date:
        return 0
    return project.daily_penalty * (end_date - project.due_date)


def get_gain(
    X: gurobipy.tupledict,
    project: Project,
    horizon: int,
    qualifications: list[str],
    staff: list[Employee],
) -> int:
    end_date: int = get_end_date(X, project, horizon, qualifications, staff)
    if end_date == -1:
        return 0

    return project.gain - get_penalty(project, end_date)


def get_end_date(
    X: gurobipy.tupledict,
    project: Project,
    horizon: int,
    qualifications: list[str],
    staff: list[Employee],
) -> int:
    end_date: int = 0
    for q, qualification in enumerate(qualifications):
        nb_days: int = 0
        for j in range(horizon):
            for e in staff:
                # print(X[j, project.index, e.index, q].value)
                old_nb_days: int = nb_days
                print(X[j, project.index, e.index, q])
                nb_days += X[j, project.index, e.index, q]
                if old_nb_days < nb_days and end_date < j:
                    end_date = j
        if nb_days < project.working_days_per_qualification[q]:
            return -1
    return end_date + 1


def solve_problem(
    horizon: int,
    qualifications: list[str],
    staff: list[Employee],
    projects: list[Project],
) -> any:
    profits_projects: dict = {
        (project.index, day): get_profit(project, day)
        for project in projects
        for day in range(horizon)
    }
    print(profits_projects)

    model: gurobipy.Model = gurobipy.Model()

    X = model.addVars(
        horizon,
        len(projects),
        len(staff),
        len(qualifications),
        vtype=gurobipy.GRB.BINARY,
        name="X",
    )

    Y = model.addVars(
        len(projects),
        len(staff),
        len(qualifications),
        vtype=gurobipy.GRB.BINARY,
        name="Y",
    )

    Z = model.addVars(
        len(projects),
        vtype=gurobipy.GRB.BINARY,
        name="Z",
    )

    A = model.addVars(
        len(projects),
        vtype=gurobipy.GRB.INTEGER,
        name="A",
    )

    model.update()

    model.setObjective(
        gurobipy.quicksum(
            # get_gain(X, project, horizon, qualifications, staff)
            project.gain
            for project in projects
            # Z[project.index] * profits_projects[project.index, horizon]
            # for project in projects
        ),
        gurobipy.GRB.MAXIMIZE,
    )

    # Add constraints

    # Contrainte 1 : Un projet doit être réalisé dans un nombre de jours consécutifs
    # model.addConstrs(
    #
    # )

    # Contrainte 2 : Un employé peut être affecté à une qualification du projet uniquement s'il a cette compétence
    model.addConstrs(
        X[j, p.index, e.index, q] == 0
        for j in range(horizon)
        for p in projects
        for e in staff
        for q, qualification in enumerate(qualifications)
        if qualification not in e.qualifications
    )

    # Contrainte 3 : Un employé peut être affecté à une seule qualification tout au long du projet
    # Number of qualifications per employee per project <= 1
    # model.addConstrs(
    #     gurobipy.quicksum(
    #         Y[p.index, e.index, q]
    #         for q in range(len(qualifications))
    #     ) <= 1
    #     for p in projects
    #     for e in staff
    # )

    # # Contrainte 4 : Un employé peut être affecté à un seul projet par jour
    model.addConstrs(
        gurobipy.quicksum(X[j, p, e, q] for p, project in enumerate(projects)) <= 1
        for q, qualification in enumerate(qualifications)
        for j in range(horizon)
        for e, employee in enumerate(staff)
    )

    # # Contrainte 5 : Un employé ne doit pas travailler un jour de congés
    model.addConstrs(
        X[j, p, e, q] == 0
        for j in range(horizon)
        for p, project in enumerate(projects)
        for e, employee in enumerate(staff)
        for q, qualification in enumerate(qualifications)
        if j in employee.vacations
    )

    # Contrainte 6 : Un projet est réalisé lorsque chaque qualification a été staffé le bon nombre de jours
    # Contrainte 7 : Un projet ne peut être réalisé qu'une seule fois
    for project in projects:
        exprs: list = []
        for q, qualification in enumerate(qualifications):
            expr1 = gurobipy.LinExpr()
            for j in range(horizon):
                for e in staff:
                    expr1 += X[j, project.index, e.index, q]
            exprs.append(
                expr1,
                gurobipy.GRB.EQUAL,
                project.working_days_per_qualification.get(qualification, 0),
            )
        model.addConstr(Z[project.index] == (gurobipy.quicksum(exprs) == len(exprs)))

    # Contrainte 8 : Le problème se déroule sur un horizon de temps donné

    # Get end date of project
    for project in projects:
        expr1 = gurobipy.LinExpr()

    # expr1 = gurobipy.LinExpr()
    # for j in range(len(instance_reduce_value)):
    #     if (j >= price_K * i) & (j < price_K * (i + 1)):
    #         expr1 += vars[j]
    # model.addConstr(expr1, GRB.EQUAL, 1)

    model.optimize()
    if model.Status == gurobipy.GRB.OPTIMAL:
        print(model.objVal)
        return model.objVal


def get_profit(project: Project, end_date: int) -> int:
    if project.due_date >= end_date:
        return project.gain
    return project.gain - project.daily_penalty * (end_date - project.due_date)


if __name__ == "__main__":
    main()
