import numpy as np
import json
import os
import cv2
from modules.draw import Plotter3d, draw_poses
from modules.parse_poses import parse_poses
from modules.inference_engine_pytorch import InferenceEnginePyTorch



def rotate_poses(poses_3d, R, t):
    R_inv = np.linalg.inv(R)
    for pose_id in range(len(poses_3d)):
        pose_3d = poses_3d[pose_id].reshape((-1, 4)).transpose()
        pose_3d[0:3, :] = np.dot(R_inv, pose_3d[0:3, :] - t)
        poses_3d[pose_id] = pose_3d.transpose().reshape(-1)

    return poses_3d


model = 'human-pose-estimation-3d.pth'
device = 'GPU'
stride = 8
base_height = 256
fx = -1
delay = 1
esc_code = 27
p_code = 112
space_code = 32
mean_time = 0
net = InferenceEnginePyTorch(model, device)
canvas_3d = np.zeros((720, 1280, 3), dtype=np.uint8)
plotter = Plotter3d(canvas_3d.shape[:2])
canvas_3d_window_name = 'Canvas 3D'
cv2.namedWindow(canvas_3d_window_name)
cv2.setMouseCallback(canvas_3d_window_name, Plotter3d.mouse_callback)
file_path = os.path.join('data', 'extrinsics.json')
with open(file_path, 'r') as f:
    extrinsics = json.load(f)
R = np.array(extrinsics['R'], dtype=np.float32)
t = np.array(extrinsics['t'], dtype=np.float32)
cap = cv2.VideoCapture(0)


while True:
    current_time = cv2.getTickCount()
    ref, frame = cap.read()
    input_scale = base_height / frame.shape[0]
    scaled_img = cv2.resize(frame, dsize=None, fx=input_scale, fy=input_scale)
    scaled_img = scaled_img[:, 0:scaled_img.shape[1] - (scaled_img.shape[1] % stride)]  # better to pad, but cut out for demo
    if fx < 0:  # Focal length is unknown
        fx = np.float32(0.8 * frame.shape[1])

    inference_result = net.infer(scaled_img)
    poses_3d, poses_2d = parse_poses(inference_result, input_scale, stride, fx)
    print(100*'-')
    print('This is Poses_3D',poses_3d.shape)
    print('This is Poses_2D',poses_2d.shape)
    # features, heatmap, paf_map = inference_result
    # print(features.shape, heatmap.shape, paf_map.shape)
    edges = []
    if len(poses_3d):
        poses_3d = rotate_poses(poses_3d, R, t)
        poses_3d_copy = poses_3d.copy()
        x = poses_3d_copy[:, 0::4]
        y = poses_3d_copy[:, 1::4]
        z = poses_3d_copy[:, 2::4]
        poses_3d[:, 0::4], poses_3d[:, 1::4], poses_3d[:, 2::4] = -z, x, -y
        poses_3d = poses_3d.reshape(poses_3d.shape[0], 19, -1)[:, :, 0:3]
        edges = (Plotter3d.SKELETON_EDGES + 19 * np.arange(poses_3d.shape[0]).reshape((-1, 1, 1))).reshape((-1, 2))
    plotter.plot(canvas_3d, poses_3d, edges)
    print(canvas_3d.shape)
    cv2.imshow(canvas_3d_window_name, canvas_3d)

    draw_poses(frame, poses_2d)
    current_time = (cv2.getTickCount() - current_time) / cv2.getTickFrequency()
    if mean_time == 0:
        mean_time = current_time
    else:
        mean_time = mean_time * 0.95 + current_time * 0.05
    cv2.putText(frame, 'FPS: {}'.format(int(1 / mean_time * 10) / 10),
                (40, 80), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255))
    cv2.imshow('ICV 3D Human Pose Estimation', frame)

    key = cv2.waitKey(delay)
    if key == esc_code:
        break
    if key == p_code:
        if delay == 1:
            delay = 0
        else:
            delay = 1
    if delay == 0:  # allow to rotate 3D canvas while on pause
        key = 0
        while (key != p_code
               and key != esc_code
               and key != space_code):
            plotter.plot(canvas_3d, poses_3d, edges)
            cv2.imshow(canvas_3d_window_name, canvas_3d)
            key = cv2.waitKey(33)
        if key == esc_code:
            break
        else:
            delay = 1



