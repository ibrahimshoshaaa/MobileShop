from .erp_engine import ERPCommandEngine
from .completion import install_completion
ERPCommandEngine = install_completion(ERPCommandEngine)
__all__=['ERPCommandEngine']
