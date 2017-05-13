from tensorflow.python.lib.io import file_io
import argparse
from datetime import datetime
from pandas import read_csv
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from keras.utils import np_utils
from keras.models import Sequential
from keras.layers import Dense, Activation, Dropout, LSTM, Conv1D
from keras.callbacks import TensorBoard
from numpy import array

#model parameters
epochs= 100
batch_size= 100
validation_split = 0.2
dropout = 0.2
pool_size = 2
timesteps = 20
timesteps_in_future = 10

def train_model(train_file='data.csv', job_dir='./tmp/exermote_train', **args):
    logs_path = job_dir + '/logs/' + datetime.now().isoformat()
    print('-----------------------')
    print('Using train_file located at {}'.format(train_file))
    print('Using logs_path located at {}'.format(logs_path))
    print('-----------------------')

    # load data
    file_stream = file_io.FileIO(train_file, mode='r')
    dataframe = read_csv(file_stream, header=0)
    dataframe.fillna(0, inplace=True)
    dataset = dataframe.values

    X = dataset[:, [
        2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
        # Device: xGravity, yGravity, zGravity, xAcceleration, yAcceleration, zAcceleration, pitch, roll, yaw, xRotationRate, yRotationRate, zRotationRate
        # 14,15,16,17,                        # Right Hand: rssi, xAcceleration, yAcceleration, zAcceleration
        # 18,19,20,21,                        # Left Hand: rssi, xAcceleration, yAcceleration, zAcceleration
        # 22,23,24,25,                        # Right Foot: rssi, xAcceleration, yAcceleration, zAcceleration
        # 26,27,28,29,                        # Left Foot: rssi, xAcceleration, yAcceleration, zAcceleration
        # 30,31,32,33,                        # Chest: rssi, xAcceleration, yAcceleration, zAcceleration
        # 34,35,36,37                         # Belly: rssi, xAcceleration, yAcceleration, zAcceleration
    ]].astype(float)
    y = dataset[:, 0]  # ExerciseType (Index 1 is ExerciseSubType)

    # data parameters
    data_dim = X.shape[1]
    num_classes = len(set(y))

    # scale X
    scaler = MinMaxScaler(feature_range=(0, 1))
    X = scaler.fit_transform(X)  # X*scaler.scale_+scaler.min_ (columnwise)

    # encode Y
    encoder = LabelEncoder()
    encoder.fit(y)
    encoded_y = encoder.transform(y)  # encoder.classes_
    hot_encoded_y = np_utils.to_categorical(encoded_y)

    # prepare data for LSTM
    def create_LSTM_dataset(x, y, timesteps):
        dataX, dataY = [], []
        for i in range(len(x) - timesteps + 1):
            dataX.append(x[i:i + timesteps, :])
            dataY.append(y[i + timesteps - timesteps_in_future, :])
        return array(dataX), array(dataY)

    X, hot_encoded_y = create_LSTM_dataset(X, hot_encoded_y, timesteps)

    # define model
    model = Sequential([
        Conv1D(32, 3, strides=2, activation='relu', input_shape=(timesteps, data_dim), name='input_x'),
        Conv1D(32, 3, strides=1, activation='relu'),
        LSTM(32, return_sequences=True),
        LSTM(32, return_sequences=False),
        Dropout(dropout),
        Dense(num_classes),
        Activation('softmax', name='output_y'),
    ])

    model.summary()

    # compile model
    model.compile(optimizer='rmsprop',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    tensor_board = TensorBoard(log_dir=logs_path, histogram_freq=1, write_graph=False, write_images=False)

    history = model.fit(X, hot_encoded_y,
                        batch_size=batch_size,
                        epochs=epochs,
                        verbose=1,
                        validation_split=validation_split,
                        callbacks=[tensor_board]
                        )
    
    model.save('model.h5')
    
    # Save model.h5 on to google storage
    with file_io.FileIO('model.h5', mode='r') as input_f:
        with file_io.FileIO(job_dir + '/model.h5', mode='w+') as output_f:
            output_f.write(input_f.read())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # Input Arguments
    parser.add_argument(
      '--train-file',
      help='GCS or local paths to training data',
      required=True
    )
    parser.add_argument(
      '--job-dir',
      help='GCS location to write checkpoints and export models',
      required=True
    )
    args = parser.parse_args()
    arguments = args.__dict__
    
    train_model(**arguments)