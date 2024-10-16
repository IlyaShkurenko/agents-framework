from abc import ABC, abstractmethod

class BaseComponent(ABC):
    """
    Base class for all components (agents and tools).
    """

    @property
    @abstractmethod
    def name(self):
        """
        Returns the name of the component.
        """
        pass

    @property
    @abstractmethod
    def description(self):
        """
        Returns the description of the component.
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs):
        """
        Method to execute the component's logic.
        """
        pass
