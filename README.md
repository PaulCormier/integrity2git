# Export MKS (PTC) Integrity to GIT
	* This python script will export the project history from MKS (PTC) Integrity to a GIT repository
	* Currently imports checkpoints and development paths only
	* This does not currently support incremental imports

## HOW TO USE
	1. You must have python, si (MKS/PTC command line tools), and git on the PATH variable
	2. Instal gitpython module: ```pip install GitPython```
		* Offine: ```pip install libs/*```
	3. Make a folder for where you want your git repository to reside
	4. Initialize the git repository by running ```git init```
	5. Execute the respective command for cygwin 
	```./mks_checkpoints_to_git.py <MKS_project_path/project.pj> | git fast-import``` 
	or for windows ```python mks_checkpoints_to_git.py <MKS_project_path/project.pj> | git fast-import``` 
	from within the initialized git repository (this will take awhile depending on how big your project is)
		* You may need to execute ```export MSYS_NO_PATHCONV=1``` to prevent Git Bash from expanding the path to the project file.
		* If you need to change the date format add the parameters: ```--date-format "<format directives>"``` with the format directives you wish to use.
	6. Once the import is complete, git will output import statistics
	7. Run ```git reset head --hard``` to resynchronize your git folder.
