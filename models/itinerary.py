class Itinerary:
    def __init__(self, id=None, name=None, content=None, destination=None, duration=None, budget=None, preferences=None, user_name=None):
        self.id = id
        self.name = name
        self.content = content
        self.destination = destination
        self.duration = duration
        self.budget = budget
        self.preferences = preferences
        self.user_name = user_name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'destination': self.destination,
            'duration': self.duration,
            'budget': self.budget,
            'preferences': self.preferences,
            'user_name': self.user_name
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            content=data.get('content'),
            destination=data.get('destination'),
            duration=data.get('duration'),
            budget=data.get('budget'),
            preferences=data.get('preferences'),
            user_name=data.get('user_name')
        )