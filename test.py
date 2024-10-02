from contextlib import contextmanager
import sys
import importlib.util
import json
import os
import traceback
import threading
from datetime import datetime

class DataProcessor:
    def __init__(self, filename, timeout):
        self.filename = filename
        self.module = None
        self.timeout = timeout

    def _import_module(self, file_path, module_name):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            raise ImportError(f"Cannot import module from {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    def _load_module(self):
        """Load the module from the given filename."""
        if not os.path.isfile(self.filename):
            raise FileNotFoundError(f"File {self.filename} does not exist")
        
        spec = importlib.util.spec_from_file_location("module.name", self.filename)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def execute_on_create(self, data):
        """Execute the on_create function from the dynamically loaded module."""
        if self.module is None:
            self._load_module()
        
        if hasattr(self.module, 'on_create'):
            return self.module.on_create(data)
        else:
            raise AttributeError("The module does not have an 'on_create' function.")
    
    def execute_on_receive(self, data):
        """Execute the on_receive function from the dynamically loaded module."""
        if self.module is None:
            self._load_module()
        
        if hasattr(self.module, 'on_receive'):
            return self.module.on_receive(data)
        else:
            raise AttributeError("The module does not have an 'on_receive' function.")
        
    def execute_on_destroy(self):
        """Execute the on_destroy function from the dynamically loaded module."""
        if self.module is None:
            self._load_module()
        
        if hasattr(self.module, 'on_destroy'):
            return self.module.on_destroy()
        else:
            raise AttributeError("The module does not have an 'on_destroy' function.")
    
    def execute_with_timeout(self, func, *args):
        """Run a function with a timeout."""
        result = None
        exception = None
        def target():
            nonlocal result, exception
            try:
                result = func(*args)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(self.timeout)

        if thread.is_alive():
            raise TimeoutError(f"Execution timed out after {self.timeout} seconds")
        if exception:
            raise exception

        return result


class ProcessEvent:
    def __init__(self, processor: DataProcessor): 
        self.processor = processor

    @contextmanager
    def stdout_interceptor(self, message_builder):
        """Context manager to temporarily replace sys.stdout with OutputInterceptor."""
        old_stdout = sys.stdout
        sys.stdout = OutputInterceptor(old_stdout, message_builder)
        try:
            yield
        finally:
            sys.stdout = old_stdout  # Revert back to original stdout after block

    def filter_processor_traceback(self, exc):
        """Filter the traceback to show only the frames related to the processor module."""
        tb = exc.__traceback__
        filtered_tb = []

        while tb is not None:
            frame = tb.tb_frame
            # Filter by the file path of the processor script
            if self.processor.filename in frame.f_code.co_filename:
                filtered_tb.append(tb)
            tb = tb.tb_next

        # Format the filtered traceback
        if filtered_tb:
            return ''.join(traceback.format_list(traceback.extract_tb(filtered_tb[0])))
        else:
            return "No relevant stack trace found from the processor script."

    def start_listening(self):
        for line in sys.stdin:
            try:
                event = json.loads(line.strip())
            except (TypeError, ValueError):
                # If the result is not deserializable
                raise(ValueError(f"Invalid input format: {line}"))

            event_type = event.get("Event")
            event_data = event.get("Data")

            try:
                with self.stdout_interceptor(get_standard_output_message):
                    if event_type == "OnCreate":
                        result = self.processor.execute_with_timeout(self.processor.execute_on_create, event_data)
                    elif event_type == "OnReceive":
                        result = self.processor.execute_with_timeout(self.processor.execute_on_receive, event_data)
                    elif event_type == "OnDestroy":
                        result = self.processor.execute_with_timeout(self.processor.execute_on_destroy)
                    else:
                        print_error(event_type, f"Unknown event type: {event_type}")
                        continue
            except TimeoutError as e:
                print_error(event_type, f"Error: Function timed out")
                continue
            except Exception as e:
                processor_traceback = self.filter_processor_traceback(e)
                print_error(event_type, f"Error: {str(e)}\nProcessor traceback:\n{processor_traceback}")
                continue
            
            # Check if the result is None, and if so, assign a default JSON
            if result is None:
                result = {"status": "default", "message": "No result generated"}

            # Attempt to serialize the result to check if it's valid JSON
            try:
                if isinstance(result, dict):
                    output = json.dumps(result)
                else:
                    raise TypeError()
            except (TypeError, ValueError):
                # If the result is not serializable
                print_error(event_type, f"Invalid result format. Expecting a dictionary, got {type(result).__name__}: {result}")
                continue
            
            print_output(event_type, "ok", output)

class OutputInterceptor:
    """Interceptor to capture stdout and send each print immediately as an event."""
    def __init__(self, original_stdout, message_builder):
        self.original_stdout = original_stdout
        self.message_builder = message_builder
    
    def write(self, message):
        if message.strip():  # Avoid sending empty lines
            self.original_stdout.write(self.message_builder(message.strip()))
            self.original_stdout.flush()
    
    def flush(self):
        pass  # No buffering, just pass through

def print_error(event, message):
    print(message + "\n", file=sys.stderr)
    sys.stderr.flush()  # Ensure the error message is flushed

    result = {"status": "error", "message": "see error log for details"}
    print_output(event, "error", json.dumps(result))

def print_output(event, status, message):
    print(json.dumps({"Event": event, "Status": status, "Data": message}))
    sys.stdout.flush()  # Ensure the output is flushed

def get_standard_output_message(message):
    return json.dumps({"Event": "StandardOutput", "Status": "ok", "Data": message}) + "\n"

# Usage example

def print_current_time():
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    print("Current time:", current_time)
    return now

def main():
    filepath = "another_main.py"
    processor = DataProcessor(filepath, 60)

    create_data = {"foo": "20"}
    on_create_result = processor.execute_on_create(create_data)

    print("on_create result:", on_create_result)

    receive_data = {
        "bar": "10"
    }
    on_receive_result = processor.execute_on_receive(receive_data)

    print("on_receive result:", on_receive_result)

if __name__ == "__main__":
    main()