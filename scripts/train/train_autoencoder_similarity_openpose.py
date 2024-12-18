import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras import models
import numpy as np
from tensorflow.keras.callbacks import TensorBoard
import datetime
import os
import json
from tensorflow.keras.layers import LSTM,Dense,GRU, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.models import load_model,Model
from tensorflow.keras.layers import Input, LSTM, Dense, Dropout, RepeatVector, TimeDistributed
from keras.utils import plot_model
from keras.losses import CosineSimilarity
from customcallback import CustomCallback

def read_all_jsons(folder_path):
    poses_per_swing = {}
    for filename in os.listdir(folder_path):
        json_data = []
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r') as file:
                data = json.load(file)
                json_data.append(data)
                poses_per_swing[filename] = json_data
    return poses_per_swing
folder_path = "/mnt/crucial1tb_ssd/cs230/data/dataset/Tennis Player Actions Dataset for Human Pose Estimation/annotations"
poses_per_swing = read_all_jsons(folder_path)

def normalize_input(input_data, mean_X, std_X):
    return (input_data - mean_X) / std_X

swings = ["backhand.json", "forehand.json", "ready_position.json", "serve.json"]

def get_autoencoder(input_shape):
    inputs = Input(shape=input_shape)
    encoded = LSTM(24, activation='relu', return_sequences=False, dropout=0.1)(inputs)
    encoded = Dropout(0.2)(encoded)
    encoded = Dense(input_shape[1], activation='relu')(encoded)
    decoded = RepeatVector(input_shape[0])(encoded)
    decoded = LSTM(24, dropout=0.2,  activation='relu', return_sequences=True)(decoded)
    decoded = TimeDistributed(Dense(input_shape[1], activation="sigmoid"))(decoded)
    autoencoder = Model(inputs, decoded)
    autoencoder.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001, clipnorm=1.0), loss="mse", metrics=['accuracy'])
    return autoencoder

for swing in swings:
    X = []
    time_step_size = 4
    epochs = 1000
    for idx in range(0,len(poses_per_swing[swing][0]["annotations"]),time_step_size):
        temp_X = []
        for i in range(idx,idx+time_step_size):
            temp_X.append(poses_per_swing[swing][0]["annotations"][i]["keypoints"])
        X.append(temp_X)

    X = np.array(X)
    mean_X = np.mean(X, axis=0)
    std_X = np.std(X, axis=0)
    std_X[std_X == 0] = 1
    X = normalize_input(X, mean_X, std_X)

    """ # Train the autoencoder model """
    np.save("models/means/mean_X_" + swing + ".npy", mean_X) ## TODO: add the normalization values to the model
    np.save("models/means/std_X_" + swing + ".npy", std_X)
    print("Checking for NaN values in X:", np.isnan(X).any())
    print("Checking for infinite values in X:", np.isinf(X).any())

    log_dir = "logs/autoencoder/" + swing + "/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tensorboard_callback = TensorBoard(log_dir=log_dir, histogram_freq=1)
    early_stopping_callback = EarlyStopping(monitor='val_loss', patience=20, restore_best_weights=False)

    tf.keras.backend.clear_session()
    input_shape = (X.shape[1], X.shape[2])
    autoencoder = get_autoencoder(input_shape)
    print("Autoencoder model summary:")
    autoencoder.summary()
    autoencoder.fit(X, X, epochs=epochs, batch_size=2, validation_split=0.2, callbacks=[CustomCallback(), tensorboard_callback, early_stopping_callback])
    autoencoder.save("models/autoencoder/" + swing + '.autoencoder.keras')

    print("Encoder model summary:")
    encoder = Model(autoencoder.input, autoencoder.layers[3].output)
    encoder.summary()
    encoder.save("models/encoder/" + swing + '.encoder.keras')
    # Use the layers of the encoder model to generate the embeddings
    embeddings = encoder.predict(X)
    np.save("models/embeddings/" + swing + '.encoder.embeddings.npy', embeddings)


    # Use the layers of the classifcation model to generate the embeddings
    classification_model = load_model('models/classification/stroke_classification.keras')
    similarity_model = Model(inputs=classification_model.inputs, outputs=classification_model.layers[-2].output)
    # Summary of the new model
    similarity_model.summary()
    # Extract embeddings from the training data
    embeddings = similarity_model.predict(X)
    np.save("models/embeddings/" + swing + '.classification.embeddings.npy', embeddings)