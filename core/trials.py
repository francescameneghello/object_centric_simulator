import simpy

class MessageBoard:
    def __init__(self, env):
        self.env = env
        self.messages = []          # Stores all messages
        self.new_message_event = simpy.Event(env)  # Event for notifying listeners

    def add_message(self, msg):
        self.messages.append(msg)
        # Trigger a new event to notify listeners
        if not self.new_message_event.triggered:
            self.new_message_event.succeed(value=msg)
        # Prepare a new event for the next message
        self.new_message_event = simpy.Event(self.env)

def listener(env, board, name):
    while True:
        msg = yield board.new_message_event
        print(f"[{env.now}] {name} received new message: {msg}")
        print(f"[{env.now}] {name} sees all messages: {board.messages}")

def message_generator(env, board):
    messages = ["Hello", "How are you?", "SimPy is fun!", "Keep all messages!"]
    for msg in messages:
        yield env.timeout(1)
        board.add_message(msg)

env = simpy.Environment()
board = MessageBoard(env)

# Start listeners
env.process(listener(env, board, "Listener 1"))
env.process(listener(env, board, "Listener 2"))

# Start message generator
env.process(message_generator(env, board))

env.run()