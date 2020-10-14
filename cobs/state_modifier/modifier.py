class StateModifier:
    def __init__(self):
        self.models = list()

    def add_model(self, model):
        self.models.append(model)

    def get_update_states(self, true_state, environment):
        for model in self.models:
            model.step(true_state, environment)

    def get_ignore_by_checkpoint(self):
        ignore_set = set()
        for model in self.models:
            if hasattr(model, 'ignore_by_checkpoint'):
                ignore_set = ignore_set.union(set(model.ignore_by_checkpoint()))
        return ignore_set
