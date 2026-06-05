import abc

class BaseProvider(abc.ABC):
    """
    Interface base para todos os provedores de dados.
    Um provedor é um "dumb pipe" que fornece dados em bruto, sem se preocupar
    com o que está dentro deles.
    """

    @abc.abstractmethod
    def connect(self):
        """Estabelece a ligação à fonte de dados."""
        pass

    @abc.abstractmethod
    def read_data(self):
        """
        Lê um chunk de dados em bruto.
        Retorna:
            bytes: array de bytes bruto recolhido.
        """
        pass

    @abc.abstractmethod
    def disconnect(self):
        """Fecha a ligação."""
        pass
