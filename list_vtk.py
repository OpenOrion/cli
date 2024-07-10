import pkgutil

vtk_modules = [name for _, name, _ in pkgutil.iter_modules() if name.startswith('vtkmodules')]
for module in sorted(vtk_modules):
    print(module)
