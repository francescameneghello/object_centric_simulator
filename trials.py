import simpy


class BroadcastChannel:
    def __init__(self, env):
        self.env = env
        self.subscribers = []

    def subscribe(self, condition=None):
        evt = self.env.event()
        self.subscribers.append((evt, condition))
        return evt

    def publish(self, message):
        for evt, condition in self.subscribers:
            if not evt.triggered:
                if condition is None or condition(message):
                    evt.succeed(message)

        # Remove triggered subscribers
        self.subscribers = [
            (evt, cond) for evt, cond in self.subscribers
            if not evt.triggered
        ]


# -------------------------
# Processes
# -------------------------

def publisher(env, channel):
    yield env.timeout(2)
    print(f"{env.now}: Publishing ('A', 'REMOVE')")
    channel.publish(("A", "REMOVE"))

    yield env.timeout(2)
    print(f"{env.now}: Publishing ('A', 'READY')")
    channel.publish(("A", "READY"))

    yield env.timeout(2)
    print(f"{env.now}: Publishing ('C', 'DONE')")
    channel.publish(("C", "DONE"))


def subscriber_wait_ready(env, name, channel):
    print(f"{env.now}: {name} waiting for READY")

    evt = channel.subscribe(lambda m: m[1] == "READY")
    msg = yield evt

    print(f"{env.now}: {name} received READY -> {msg}")


def subscriber_wait_done(env, name, channel):
    print(f"{env.now}: {name} waiting for DONE")

    evt = channel.subscribe(lambda m: m[1] == "DONE")
    msg = yield evt

    print(f"{env.now}: {name} received DONE -> {msg}")

    yield env.timeout(2)
    evt = channel.subscribe(lambda m: m[1] == "DONE")
    msg = yield evt

    print(f"{env.now}: {name} received DONE -> {msg}")


# -------------------------
# Simulation Setup
# -------------------------

env = simpy.Environment()
channel = BroadcastChannel(env)

env.process(publisher(env, channel))
env.process(subscriber_wait_ready(env, "Subscriber1", channel))
env.process(subscriber_wait_done(env, "Subscriber2", channel))

env.run()
'''received = []

while len(received) < 2:
    msg = yield mailboxes["B"].get(lambda m: m[1] == "READY")
    received.append(msg)

print("Received at least 2 messages:", received)

results = yield simpy.AllOf(env, events)
#results = yield simpy.AnyOf(env, events)
'''


