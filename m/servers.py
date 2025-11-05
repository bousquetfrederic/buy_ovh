import m.api
import m.print

__all__ = ['servers_specs']

servers_specs_list = []

def servers_specs(printMessage=False):
    m.print.print_servers(m.api.get_servers_list(printMessage))
    input("Press Enter.")
