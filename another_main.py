from calculator.helper import Calculator

class MyClass:
    def __init__(self):
        self.calculator = Calculator()

    def perform_calculation(self, a, b):
        result = self.calculator.add(a, b)
        print(f"The sum of {a} and {b} is: {result}")

# Example usage

my_calculator = Calculator()
foo_value = None
bar_value = None

def on_create(data: dict) -> dict | None:
    global foo_value
    foo_value = float(data.get("foo", 0))
    return {
        "initialized_foo": foo_value
    }

def on_receive(data: dict) -> dict:
    """
    Process received event data, concatenating 'foo' and 'bar' to creatre 'foo_bar'.

    Args:
        data (dict): Received event data containing new 'bar' value.

    Returns:
        dict: Result of processing the event data, including a 'foo_bar' value.
    """
    global bar_value
    bar_value = float(data.get("bar", bar_value))
    
    # Calculate foo_bar by concatenating foo and bar
    foo_bar = f"{foo_value}_{bar_value}"

    print("executing on_receive of another_main.py from a public repo")
    
    return {
        "foobar": foo_bar,
        "sum": f"{foo_value} + {bar_value} = {my_calculator.add(foo_value, bar_value)}",
        "diff": f"{foo_value} - {bar_value} = {my_calculator.subtract(foo_value, bar_value)}",
        "product": f"{foo_value} * {bar_value} = {my_calculator.multiply(foo_value, bar_value)}"
    }

def on_destroy() -> dict | None:
    """
    Clean up resources when the script is being destroyed.

    Returns:
        dict: Final values of 'foo' and 'bar'.
    """
    global foo_value, bar_value
    return {
        "final_foo": foo_value,
        "final_bar": bar_value
    }