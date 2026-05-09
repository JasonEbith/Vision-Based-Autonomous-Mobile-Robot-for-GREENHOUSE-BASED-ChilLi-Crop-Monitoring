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

### Rover Operation in Pest Detection Mode (Sensor Deployment Configuration)
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/570f6824951c629f717cee726a081aa3ac55697e/rover2.jpg)

###  Real-Time Pest Detection Using YOLO Model
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/23f8d70c97bb1faf25f3a01a933a0109f1104121/pest.png)

### Real-Time Row Detection and Navigation Control Output
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/279907e314bab15631fe5e65cafe735f8a94892d/row.png)

### Dashboard Interface Displaying Live Monitoring and Detection Logs
![Alt text](https://github.com/JasonEbith/Vision-Based-Autonomous-Mobile-Robot-for-GREENHOUSE-BASED-ChilLi-Crop-Monitoring/blob/daa82d54f034d7892b98dc78efdab8d6d040a5ed/dash.png)

The dashboard displays:
* Live camera feed
* Pest detection logs
* Plant count
* Moisture status
