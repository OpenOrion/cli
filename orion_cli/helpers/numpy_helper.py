from typing import Annotated, Optional, Union
import numpy as np
from pydantic import BeforeValidator, ConfigDict, PlainSerializer


NdArray = Annotated[
    np.ndarray,
    BeforeValidator(lambda arr: np.array(arr)),  # Ensure input is a numpy array
    PlainSerializer(lambda arr:  arr.tolist(), return_type=list),
]