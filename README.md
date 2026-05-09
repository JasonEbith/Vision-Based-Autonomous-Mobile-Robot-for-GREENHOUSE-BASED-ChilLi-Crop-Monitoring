# Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring
## Introduction
This project presents an autonomous greenhouse monitoring rover developed for chilli crop monitoring and inspection. The system combines computer vision, deep learning, embedded control, and sensor integration to perform row-based navigation, plant disease detection, and soil moisture monitoring in greenhouse environments.
The rover uses a Raspberry Pi 5 for image processing and AI-based disease detection, while an ESP32 handles motor control and servo actuation. A YOLO-based deep learning model is used to detect chilli plant diseases such as aphids, whiteflies, anthracnose, leaf spot, and armyworm. The system also includes a dashboard for real-time monitoring.

## Main Features
* Autonomous row-based navigation using computer vision
* YOLO-based chilli plant disease detection
* Soil moisture monitoring using YL-69 sensor
* Real-time dashboard interface
* Differential drive motor control
* Servo-based camera and sensor positioning
* Serial communication between Raspberry Pi and ESP32
  
## Hardware Components
* Raspberry Pi 5
* ESP32
* Raspberry Pi Camera Module v2 (8MP)
* 4 BO Motors
* 2 × L298N Motor Drivers
* PCA9685 PWM Controller
* MG90S Servo Motor (camera tilt)
* SG90 Servo Motor (YL-69 deployment)
* YL-69 Soil Moisture Sensor
* 3 × 18650 Li-ion Batteries

## Working

The Raspberry Pi camera continuously captures frames from the greenhouse environment. During navigation mode, the system performs HSV-based color segmentation and contour detection to identify crop rows and maintain alignment using proportional control.

In pest detection mode, high-resolution images are processed using a YOLO-based deep learning model to detect plant diseases. Detection results, confidence scores, and logs are displayed on the dashboard.

The Raspberry Pi sends navigation and control commands to the ESP32 through serial communication. The ESP32 controls the motors and servo actuators for rover movement, camera positioning, and moisture sensor deployment.

### Overall Prototype of Autonomous Agricultural Rover System
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/82f557c0fbd0877a1aa9a86fd95e521dc3819fcd/rover1.jpg)

###  Rover Operation in Row Navigation Mode (Navigation Configuration)
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/82f557c0fbd0877a1aa9a86fd95e521dc3819fcd/rover3.jpg)

### Overall Prototype of Autonomous Agricultural Rover System
![Alt text]([image_url]())
The dashboard displays:
* Live camera feed
* Pest detection logs
* Plant count
* Moisture status
