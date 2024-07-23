# %%
import logging

def setup_logger(verbose=True):
    # Create a logger
    logger = logging.getLogger('info_logger')
    logger.setLevel(logging.INFO)

    # Create a console handler and set its level to INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a formatter and add it to the console handler
    formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    return logger

# Usage example
logger = setup_logger()
# %%
