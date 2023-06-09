import json
import os
import cv2
import numpy as np
import numpy.matlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image #TODO delete
import bisect


# change IDs to your IDs.
ID1 = "208687129"
ID2 = "313514044"

ID = "HW3_{0}_{1}".format(ID1, ID2)
RESULTS = 'results'
os.makedirs(RESULTS, exist_ok=True)
IMAGE_DIR_PATH = "Images"

# SET NUMBER OF PARTICLES
N = 100

# Initial Settings
s_initial = [297,    # x center
             139,    # y center
              16,    # half width
              43,    # half height
               0,    # velocity x
               0]    # velocity y


def predict_particles(s_prior: np.ndarray) -> np.ndarray:
    """Progress the prior state with time and add noise.

    Note that we explicitly did not tell you how to add the noise.
    We allow additional manipulations to the state if you think these are necessary.

    Args:
        s_prior: np.ndarray. The prior state.
    Return:
        state_drifted: np.ndarray. The prior state after drift (applying the motion model) and adding the noise.
    """
    s_prior = s_prior.astype(float)
    
    # velocities vector to add to the state vector
    velocity_addition = np.zeros_like(s_prior)
    velocity_addition[0] = s_prior[-2]
    velocity_addition[1] = s_prior[-1]
    
    state_drifted = s_prior + velocity_addition 
    
    #generate noise
    mean = 0
    var_coordinates = 2
    var_velocity = 1
    var_w_h = 1
    noise_x = np.random.normal(mean, var_coordinates, N)
    noise_y = np.random.normal(mean, var_coordinates, N)
    noise_w = np.random.normal(mean, var_w_h, N)
    noise_h = np.random.normal(mean, var_w_h, N)
    noise_vx = np.random.normal(mean, var_velocity, N)
    noise_vy = np.random.normal(mean, var_velocity, N)
    
    #add noise
    state_drifted[0,:] += noise_x
    state_drifted[1,:] += noise_y
    state_drifted[2,:] += noise_w
    state_drifted[3,:] += noise_h
    state_drifted[4,:] += noise_vx
    state_drifted[5,:] += noise_vy
    
    state_drifted = state_drifted.astype(int)
    return state_drifted


def compute_normalized_histogram(image: np.ndarray, state: np.ndarray) -> np.ndarray:
    """Compute the normalized histogram using the state parameters.

    Args:
        image: np.ndarray. The image we want to crop the rectangle from.
        state: np.ndarray. State candidate.

    Return:
        hist: np.ndarray. histogram of quantized colors.
    """
    state = np.floor(state) 
    state = state.astype(int)

    # crop image
    x, y, w, h = state[0], state[1], state[2], state[3]
    cropped_image = image[max(y-h,0):min(y+h,image.shape[0]), max(x-w,0):min(x+w, image.shape[1]), :]

    # quantize colors
    cropped_image = np.floor(cropped_image/16)
    cropped_image = cropped_image.astype(int)

    # compute histogram
    hist = np.zeros((16, 16, 16))
    for i in range(cropped_image.shape[0]):
        for j in range(cropped_image.shape[1]):
            hist[cropped_image[i, j, 0], cropped_image[i, j, 1], cropped_image[i, j, 2]] += 1

    # reshape to vector
    hist = np.reshape(hist, 16 * 16 * 16)

    # normalize
    if sum(hist) > 0 : 
        hist = hist/sum(hist)

    return hist

def sample_particles(previous_state: np.ndarray, cdf: np.ndarray) -> np.ndarray:
    """Sample particles from the previous state according to the cdf.

    If additional processing to the returned state is needed - feel free to do it.

    Args:
        previous_state: np.ndarray. previous state, shape: (6, N)
        cdf: np.ndarray. cummulative distribution function: (N, )

    Return:
        s_next: np.ndarray. Sampled particles. shape: (6, N)
    """
    S_next = np.zeros(previous_state.shape)
    N = previous_state.shape[1]
    
    for n in range(N):
        r = np.random.random()
        j = np.argmax(cdf >= r)
        S_next[:, n] = previous_state[:, j]
    
    return S_next


def bhattacharyya_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Calculate Bhattacharyya Distance between two histograms p and q.

    Args:
        p: np.ndarray. first histogram.
        q: np.ndarray. second histogram.

    Return:
        distance: float. The Bhattacharyya Distance.
    """
    power = 20 * np.sum(np.sqrt(p * q))
    distance = np.exp(power)
    return distance


def show_particles(image: np.ndarray, state: np.ndarray, W: np.ndarray, frame_index: int, ID: str,
                  frame_index_to_mean_state: dict, frame_index_to_max_state: dict,
                  ) -> tuple:
    fig, ax = plt.subplots(1)
    image = image[:,:,::-1]
    plt.imshow(image)
    plt.title(ID + " - Frame mumber = " + str(frame_index))

    # Avg particle box
    (x_avg, y_avg, w_avg, h_avg) = np.average(state, axis=1,weights=W).T[:4]

    rect = patches.Rectangle((x_avg, y_avg), w_avg, h_avg, linewidth=1, edgecolor='g', facecolor='none')
    ax.add_patch(rect)

    # calculate Max particle box
    max_w = np.argmax(W)
    (x_max, y_max, w_max, h_max) = state[:,max_w].T[:4]
    
    rect = patches.Rectangle((x_max, y_max), w_max, h_max, linewidth=1, edgecolor='r', facecolor='none')
    ax.add_patch(rect)
    plt.show(block=False)

    fig.savefig(os.path.join(RESULTS, ID + "-" + str(frame_index) + ".png"))
    frame_index_to_mean_state[frame_index] = [float(x) for x in [x_avg, y_avg, w_avg, h_avg]]
    frame_index_to_max_state[frame_index] = [float(x) for x in [x_max, y_max, w_max, h_max]]
    return frame_index_to_mean_state, frame_index_to_max_state

def computer_normalized_weights(image: np.ndarray, state: np.ndarray, q: np.ndarray) -> np.ndarray:
    w = np.zeros(state.shape[1]) # initialize weights
    for i in range(state.shape[1]): # go through columns of S
        p = compute_normalized_histogram(image, state[:, i].flatten())
        w[i] = bhattacharyya_distance(p, q)

    # normalize the vector w
    w = w / np.sum(w)

    return w

def main():
    state_at_first_frame = np.matlib.repmat(s_initial, N, 1).T
    S = predict_particles(state_at_first_frame)

    # LOAD FIRST IMAGE
    image = cv2.imread(os.path.join(IMAGE_DIR_PATH, "001.png"))
    
    # COMPUTE NORMALIZED HISTOGRAM
    q = compute_normalized_histogram(image, s_initial)

    # COMPUTE NORMALIZED WEIGHTS
    W = computer_normalized_weights(image, S, q)
        
    # COMPUTE PREDICTOR CDFS (C)
    C = np.cumsum(W)
            
    images_processed = 1

    # MAIN TRACKING LOOP
    image_name_list = os.listdir(IMAGE_DIR_PATH)
    image_name_list.sort()
    frame_index_to_avg_state = {}
    frame_index_to_max_state = {}
    for image_name in image_name_list[1:]:

        S_prev = S

        # LOAD NEW IMAGE FRAME
        image_path = os.path.join(IMAGE_DIR_PATH, image_name)
        current_image = cv2.imread(image_path)

        # SAMPLE THE CURRENT PARTICLE FILTERS
        S_next_tag = sample_particles(S_prev, C)

        # PREDICT THE NEXT PARTICLE FILTERS (YOU MAY ADD NOISE)
        S = predict_particles(S_next_tag) 
        
        # COMPUTE NORMALIZED WEIGHTS
        W = computer_normalized_weights(current_image, S, q)
    
        # COMPUTE PREDICTOR CDFS (C)
        C = np.cumsum(W)

        # CREATE DETECTOR PLOTS
        images_processed += 1
        if 0 == images_processed%10:
            frame_index_to_avg_state, frame_index_to_max_state = show_particles(
                current_image, S, W, images_processed, ID, frame_index_to_avg_state, frame_index_to_max_state)

    with open(os.path.join(RESULTS, 'frame_index_to_avg_state.json'), 'w') as f:
        json.dump(frame_index_to_avg_state, f, indent=4)
    with open(os.path.join(RESULTS, 'frame_index_to_max_state.json'), 'w') as f:
        json.dump(frame_index_to_max_state, f, indent=4)

if __name__ == "__main__":
    main()
