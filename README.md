# Export Source Integrity to GIT
* This python script will export the project history from Source Integrity to a GIT repository
* Currently imports checkpoints and development paths only
* This does not currently support incremental imports

## How to use
1. You must have si (Source Integrity command line tools) and git on the PATH
2. Log into the Source Integrity client
3. Make a folder where you want your git repository to reside
4. Initialize the git repository by running ```git init```
5. In a command prompt (not PowerShell or bash) execute the command: 
```mks_checkpoints_to_git.exe <MKS_project_path/project.pj> | git fast-import``` 
from within the initialized git repository (this will take a while depending on how big your project is)
	* If you need to change the date format add the parameters: 
	```--date-format "<python format directives>"``` 
	with the format directives you wish to use
6. Once the import is complete, git will output import statistics
7. Run ```git reset head --hard``` to resynchronize your git folder
8. You can now confirm/clean up the git history, and then push it to a remote

## How to compile
1. Install Python 3.10
2. Install gitpython module: ```pip install GitPython```
3. Install pyinstaller module: ```pip install pyinstaller```
4. Execute the command ```pyinstaller --onefile mks_checkpoints_to_git.py```