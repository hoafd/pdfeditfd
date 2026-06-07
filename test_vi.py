import sys
import cv2
import numpy as np

# Create a dummy image with Vietnamese text
img = np.ones((100, 400, 3), dtype=np.uint8) * 255
cv2.putText(img, "Hoài Niệm", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
# Wait, FONT_HERSHEY_SIMPLEX doesn't support unicode accents.
