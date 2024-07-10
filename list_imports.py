# list_imports.py
import modulegraph.modulegraph

def analyze_script(script_path):
    mg = modulegraph.modulegraph.ModuleGraph()
    mg.run_script(script_path)
    for node in mg.flatten():
        print(node.identifier)

if __name__ == '__main__':
    analyze_script('orion_cli/cli.py')
