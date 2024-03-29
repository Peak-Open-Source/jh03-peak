from fastapi.responses import StreamingResponse
from .CalculationState import CalculationState
from settings import DownloadOptions, ALPHAFOLD_PATH, ALPHAFOLD_DATA_DIR, CALCULATIONS_CACHE

from io import BytesIO
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import threading
import zipfile

TERMINATION_TIMEOUT = 5 # How long Calculation.stop() should wait before assuming termination has failed and attempts to kill thread.

class Calculation(threading.Thread):
    def __init__(self, sequence: str, logger):
        self.sequence = sequence
        self.logger = logger
        self.status = CalculationState.WAITING
        self.waiting_since = time.time()
        self.start_time = None
        self.on_complete_callback = lambda:None # Function to call when calculation complete

        self.process = None
        self.process_exit_code = None
        self.output_pathname = f"{CALCULATIONS_CACHE}/{id(self)}"
        self.log = open(f"{self.output_pathname}.log", "a")

        os.mkdir(self.output_pathname)

        super().__init__()

        self.logger.info("Created calculation, instantiated")
    
    def run(self):
        """ Run the process in this thread. Does not terminate until process is complete. """
        self.status = CalculationState.CALCULATING

        # Create fasta sequence file
        with open(f"{self.output_pathname}.fasta", "w") as f:
            f.write(f">Temporary sequence file for {id(self)}|\n{self.sequence}")

        # Create command
        command = f"""python3
            {ALPHAFOLD_PATH}/docker/run_docker.py
            --fasta_paths={self.output_pathname}.fasta
            --max_template_date=9999-12-31
            --data_dir={ALPHAFOLD_DATA_DIR}
            --use_gpu=false
        """

        # Set calculation start timestamp
        self.start_time = time.time()

        # Begin execution
        command_parts = shlex.split(command)
        self.logger.info(f"Beginnning protein prediction calculation: executing: '{command_parts}'")
        self.process = subprocess.Popen(
            command_parts,
            stdout = self.log,
            stderr = self.log
        )
        self.logger.info(f"Process started.")

        # Wait for completion
        self.process_exit_code = self.process.wait()

        # Complete
        if self.process_exit_code == 0:
            self.status = CalculationState.COMPLETE
        else:
            self.status = CalculationState.FAILED

        self.on_complete_callback()
    
    def stop(self):
        """ Stop the ongoing process and terminate thread. """
        self.status = CalculationState.FAILED
        # Attempt termination of process (run will end thread once process terminated)
        self.process.terminate()
        self.join(TERMINATION_TIMEOUT)
        if not self.is_alive():
            return
        # Termination of process failed, attempt kill (run will end thread once process killed)
        self.process.kill()
        self.join(TERMINATION_TIMEOUT)
        if not self.is_alive():
            return
        # Process kill failed, attempt to stop thread directly
        self._stop_event.set()

    def get_logs(self):
        """ Returns the contents of the log file """
        logs = ""
        with open(f"{self.output_pathname}.log") as f:
            logs += f.read()
        return logs
    
    def get_results(self, download_type):
        """ Returns a FastAPI response object containing result files. """
        if self.status != CalculationState.COMPLETE:
            return False

        # Select files to return
        download_type_pattern = DownloadOptions.get(download_type, None)
        if download_type_pattern is None:
            err = f"Invalid download request '{download_type}'. Valid download requests are: '{','.join(DownloadOptions.keys())}'"
            self.logger.warning(err)
            return json.dumps({"detail":err})
               
        result_filenames = [filename for filename in os.listdir(self.output_pathname) if re.match(download_type_pattern, filename)]
        self.logger.info(f"Preparing files for download: {','.join(result_filenames)}.")

        # Return files
        result = ""
        if len(result_filenames) == 0: # No files selected, return error
            err = f"No files match specified type '{download_type}'. Files available are: {','.join(os.listdir(self.output_pathname))}"
            self.logger.warning(err)
            result = json.dumps({"detail":err})
        elif len(result_filenames) == 1: # One file selected, return as is
            with open(f"{self.output_pathname}/{result_filenames[0]}") as f:
                result = f.read()
        else: # Multiple files selected, zip and return zipfile
            result = BytesIO()

            with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED, False) as zip_file: # Open result buffer
                for filename in result_filenames:
                    zip_file.write(f"{self.output_pathname}/{filename}", filename)
            result = StreamingResponse(iter([result.getvalue()]), media_type="application/zip")
        
        return result

    def cleanup(self):
        """ Remove all files associated with this file from filesystem. """
        if self.is_alive():
            return False # Do not attempt to clean up if thread still running!
        
        self.log.close()
        try:
            os.remove(f"{self.output_pathname}.log")
        except FileNotFoundError:
            self.logger.debug("Couldn't clean log file, log file doesn't exist.")
        
        try:
            os.remove(f"{self.output_pathname}.fasta")
        except FileNotFoundError:
            self.logger.debug("Couldn't clean fasta file, fasta file doesn't exist.")
        
        try:
            shutil.rmtree(self.output_pathname)
        except FileNotFoundError:
            self.logger.debug("Couldn't clean output directory, directory doesn't exist.")
    
    def set_on_complete_callback(self, callback_fn):
        self.on_complete_callback = callback_fn

    def __str__(self):
        return json.dumps({
            "sequence": self.sequence,
            "internal_id": id(self),
            "calculation_state": str(self.status),
            "waiting_since_timestamp": self.waiting_since,
            "calculation_start_timestamp": self.start_time,
        })