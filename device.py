from abc import ABC, abstractmethod
from models import CommonModel, Model113, EndModel


class SunspecDevice(ABC):

    def __init__(self, base_addr=40000, models=list):
        self.base_addr = base_addr
        self.models = models

    def get_registers(self):
        """
        Generate and return the data block for the model.
        Must be implemented by subclasses.
        """
        data_block = []

        for model in self.models:
            data_block.extend(model.get_register())

        return data_block
        

class FerroampDevice(SunspecDevice):
    """
        Ferroamp Device class that represent a Ferroamp Energyhub 14 three-phase inverter."
"""
    def __init__(self, base_addr=40000):
        models = []
        models.append(CommonModel(Mn="Ferroamp", Md="Energyhub 14"))
        models.append(Model113())
        models.append(EndModel())
        super().__init__(base_addr, models)
