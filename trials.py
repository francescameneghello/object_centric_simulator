import simpy


def object_a(env, mailboxes):
    print(f"{env.now}: A starting work")
    yield env.timeout(1)

    yield mailboxes["B"].put(("A", "READY"))
    print(f"{env.now}: A sends READY to B")


def object_c(env, mailboxes):
    print(f"{env.now}: C starting work")
    yield env.timeout(3)

    yield mailboxes["B"].put(("C", "READY"))
    print(f"{env.now}: C sends READY to B")


def object_b(env, mailboxes):
    print(f"{env.now}: B starting work")
    yield env.timeout(2)

    events = [
        mailboxes["B"].get(lambda m: m == ("A", "READY")),
        mailboxes["B"].get(lambda m: m == ("C", "READY"))
    ]

    results = yield simpy.AllOf(env, events)
    #results = yield simpy.AnyOf(env, events)

    '''received = []

    while len(received) < 2:
        msg = yield mailboxes["B"].get(lambda m: m[1] == "READY")
        received.append(msg)

    print("Received at least 2 messages:", received)'''

    print("Received both:", list(results.values()))


env = simpy.Environment()

mailboxes = {
    "A": simpy.FilterStore(env),
    "B": simpy.FilterStore(env),
    "C": simpy.FilterStore(env)
}

env.process(object_a(env, mailboxes))
env.process(object_b(env, mailboxes))
env.process(object_c(env, mailboxes))

env.run()