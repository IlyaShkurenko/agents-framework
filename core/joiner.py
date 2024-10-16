# core/joiner.py

class Joiner:
    """
    The Joiner collects and combines results from prior actions.
    """

    def __init__(self, observations):
        self.observations = observations

    def join(self):
        """
        Joins the observations to form the final response.
        """
        responses = [str(obs) for idx, obs in sorted(self.observations.items())]
        return "\n".join(responses)
