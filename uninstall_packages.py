"""
Uninstall all installed packages
"""

import subprocess

def uninstall_all_packages():
    result = subprocess.run(['pip', 'freeze'], capture_output=True, text=True)
    packages = result.stdout.splitlines()

    for package in packages:
        package_name = package.split('==')[0] #get the package name
        subprocess.run(['pip', 'uninstall', '-y', package_name]) #add -y to bypass confirmation

    # Verify uninstallation
    print(subprocess.run(['pip', 'freeze']))

if __name__ == "__main__":
    uninstall_all_packages()