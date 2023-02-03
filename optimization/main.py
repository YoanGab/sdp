import json
import sys

import gurobipy

from .entities import ProblemData, Employee, Job


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


def solve_problem(
    data: ProblemData, max_nb_projects_per_employee: int, max_duration_project: int
) -> None:
    H: list[int] = list(range(1, data["horizon"] + 1))
    Q: list[str] = data["qualifications"]
    S: list[Employee] = data["staff"]
    J: list[Job] = data["jobs"]

    # Pour i ∈ S, un membre du personnel i est caractérisé par :
    # – un sous-ensemble de qualifications Q_i^S ⊆ Q ;
    # – un sous-ensemble de jours de congés V_i^S ⊆ H ;
    Q_i_S: dict[Employee, list[str]] = {
        employee: employee.qualifications for employee in S
    }

    V_i_S: dict[Employee, list[int]] = {employee: employee.vacations for employee in S}

    # Pour j ∈ J, un job j est caractérisé par :
    # – un sous-ensemble de qualifications Q_j^J ⊆ Q ;
    Q_j_J: dict[Job, list[str]] = {
        job: list(job.working_days_per_qualification.keys()) for job in J
    }
    # – des nombres de jours/personnes n_j,k ∈ N
    # pour chaque qualification d’intérêt k ∈ Q_j^J
    n_j_k: dict[Job, dict[str, int]] = {
        job: {
            qualification: job.working_days_per_qualification[qualification]
            for qualification in job.working_days_per_qualification
        }
        for job in J
    }
    # – un gain g_j ∈ N obtenu lorsque le job j est accompli ;
    g_j: dict[Job, int] = {job: job.gain for job in J}

    # – une pénalité financière par journée de retard c_j ∈ N
    c_j: dict[Job, int] = {job: job.daily_penalty for job in J}

    # - une date de fin d_j est prévue pour le job j
    d_j: dict[Job, int] = {job: job.due_date for job in J}

    # Create a new model
    model: gurobipy.Model = gurobipy.Model("CompuOpti")

    # Create variables
    # Xi,j,k,t ∈ {0, 1}
    # vaut 1 si
    #   la personne i réalise une qualification q pour le job j pendant la journée t,
    # 0 sinon,
    # pour i ∈ S, j ∈ J, k ∈ Q, t ∈ H.
    X = model.addVars(
        [(i, j, k, t) for i in S for j in J for k in Q for t in H],
        vtype=gurobipy.GRB.BINARY,
        name="X",
    )

    # Yj ∈ {0, 1} vaut 1 si le job j est réalisé totalement, 0 sinon, j ∈ J
    Y = model.addVars(J, vtype=gurobipy.GRB.BINARY, name="Y")

    # Lj nombre de jours de retard pour le job j ∈ J
    L = model.addVars(J, vtype=gurobipy.GRB.INTEGER, name="L")

    # Ej date de fin de réalisation du job j ∈ J
    E = model.addVars(J, vtype=gurobipy.GRB.INTEGER, name="E", lb=min(H), ub=max(H))

    Z = model.addVars(
        [(i, j) for i in S for j in J],
        vtype=gurobipy.GRB.BINARY,
        name="Z",
    )

    B = model.addVars(J, vtype=gurobipy.GRB.INTEGER, name="B", lb=min(H), ub=max(H))

    model.update()

    # maximize(Somme for j in J of (Y_j × gj − Lj × cj) Objectif: Maximizer la somme
    # des différences des gains et des pertes pour chaque projet
    model.setObjective(
        gurobipy.quicksum(Y[j] * g_j[j] - L[j] * c_j[j] for j in J),
        gurobipy.GRB.MAXIMIZE,
    )

    # Somme for j in J, k in Q of (X[i, j, k, t] <= 1 for all i in S, t in H)
    # Max of 1 qualification assigned per job for each employee for each day
    model.addConstrs(
        gurobipy.quicksum(X[i, j, k, t] for j in J for k in Q) <= 1
        for i in S
        for t in H
    )

    # Somme for j in J, k in Q of (X[i, j, k, t] = 0 for all i in S, t in V_i_S)
    # Can't work during vacations
    model.addConstrs(
        gurobipy.quicksum(X[i, j, k, t] for j in J for k in Q) == 0
        for i in S
        for t in V_i_S[i]
    )

    # X[i, j, k, t] = 0
    # for all i in S, j in J, k in Q if k not in Q_i^S or k not in Q_j^J, for t in H
    # Can't work
    #   if employee doesn't have the qualification
    #   or if job doesn't require this qualification
    model.addConstrs(
        (
            X[i, j, k, t] == 0
            for i in S
            for j in J
            for k in Q
            for t in H
            if k not in Q_i_S[i] or k not in Q_j_J[j]
        ),
    )

    # Yj × n_j,k ≤ Somme for i in S, t in H of (X[i, j, k, t] for j in J for k in Q_j^J)
    # Days worked must be superior or equal to number of days required if job is done
    model.addConstrs(
        (
            Y[j] * n_j_k[j][k] <= gurobipy.quicksum(X[i, j, k, t] for i in S for t in H)
            for j in J
            for k in Q_j_J[j]
        ),
    )

    # Somme for i in S, t in H of (X[i, j, k, t] <= n_j_k for j in J for k in Q_j^J)
    # Days worked per qualification must be inferior or equal to days required
    model.addConstrs(
        (
            gurobipy.quicksum(X[i, j, k, t] for i in S for t in H) <= n_j_k[j][k]
            for j in J
            for k in Q_j_J[j]
        ),
    )

    # Xi,j,k,t × t ≤ Ej ∀ i ∈ S, ∀ j ∈ J , ∀ k ∈ Q, ∀ t ∈ H
    # End date of a job must be superior or equal to last day of work
    model.addConstrs(
        (X[i, j, k, t] * t <= E[j] for i in S for j in J for k in Q for t in H),
    )

    # Ej − dj ≤ Lj ∀ j ∈ J
    # Number of late days must be superior or equal to end date - due date
    model.addConstrs((E[j] - d_j[j] <= L[j] for j in J))

    # Create a constraint to link Z and X
    # Z = 0 if X = 0
    model.addConstrs(
        (
            Z[i, j] <= gurobipy.quicksum(X[i, j, k, t] for t in H for k in Q)
            for i in S
            for j in J
        )
    )

    # # Z = 1 if X >= 1
    model.addConstrs(
        (Z[i, j] >= X[i, j, k, t] for i in S for j in J for k in Q for t in H)
    )

    # Max of projects per employee must be equal to max_nb_projects_per_employee
    model.addConstrs(
        (
            gurobipy.quicksum(Z[i, j] for j in J) <= max_nb_projects_per_employee
            for i in S
        )
    )

    # # Start date of a job must be inferior or equal to all days of work
    model.addConstrs(
        (B[j] * X[i, j, k, t] <= t for i in S for j in J for k in Q for t in H),
    )

    # Duration of a job must be inferior or equal to max_duration_project
    model.addConstrs((E[j] - B[j] <= max_duration_project - 1 for j in J))

    # Parameters
    model.Params.PoolSearchMode = 0
    # model.Params.PoolSolutions = 10_000
    model.Params.PoolSolutions = 1
    # model.Params.PoolGap = 0.0
    # model.Params.TimeLimit = 120

    model.optimize()

    print(f"{model.solCount} solutions")
    # solutions: set = set()
    for k in range(model.SolCount):
        if (k + 1) % 1000 == 0 and k > 100:
            print(f"\nSolution{k + 1}")
        model.Params.SolutionNumber = k
        employees = {}
        for v in model.getVars():
            if v.Xn == 0:
                continue

            if v.varName[0] == "X":
                name = v.varName[2:-1].split(",")
                employee_name: str = name[0]
                project_name: str = name[1]
                qualification: str = name[2]
                day: int = int(name[3])

                if employee_name not in employees:
                    employees[employee_name] = {"projects": {}, "schedule": {}}
                employees[employee_name]["projects"][project_name] = qualification
                employees[employee_name]["schedule"][day] = project_name

            if v.varName[0] == "B":
                print(v)

            if v.varName[0] == "E":
                print(v)
        # solutions.add(json.dumps(employees))
        print(employees, "\n\n")
    # print(len(solutions), "unique solutions")


def main() -> None:
    size: str = sys.argv[1]
    data: ProblemData = get_data(size)
    solve_problem(data, 10, 1)


if __name__ == "__main__":
    main()
