import unittest

from lightwood.helpers.device import get_devices
from lightwood.encoders.time_series import RnnEncoder
from lightwood.encoders.time_series.helpers.rnn_helpers import *


class TestRnnEncoder(unittest.TestCase):

    def test_padding(self):
        series = [[1, 2, 3], [2, 3], [3, 4, 5, 6], [4, 5, 6]]
        target = [[1.0, 2.0, 3.0, 4.0, 0.0], [2.0, 3.0, 4.0, 5.0, 0.0], [3.0, 0.0, 5.0, 6.0, 0.0]]
        result = tensor_from_series(series, get_devices()[0], n_dims=5, pad_value=0.0, max_len=3).tolist()[0]
        self.assertEqual(result, target)

    def test_normalizer(self):
        data = [[-100.0, -5.0, 0.0, 5.0, 100.0],
                [-1000.0, -50.0, 0.0, 50.0, 1000.0],
                [-500.0, -405.0, -400.0, -395.0, -300.0],
                [300.0, 395.0, 400.0, 405.0, 500.0],
                [0.0, 1e3, 1e6, 1e9, 1e12]]
        normalizer = MinMaxNormalizer()
        reconstructed = normalizer.inverse_transform(normalizer.fit_transform(data))
        self.assertTrue(np.allclose(data, reconstructed, atol=0.1))

    def test_overfit(self):
        single_dim_ts = [[[1, 2, 3, 4, 5]],
                     [[2, 3, 4, 5, 6]],
                     [[3, 4, 5, 6, 7]],
                     [[4, 5, 6, 7, 8]]]

        multi_dim_ts = [[[1, 2, 3, 4, 5, 6],
                         [2, 3, 4, 5, 6, 7],
                         [3, 4, 5, 6, 7, 8],
                         [4, 5, 6, 7, 8, 9]]]

        single_qry_ans = ([[[1, 2, 3]], [[2, 3, 4]], [[3, 4, 5]], [[4, 5, 6]]],  # query
                          [4, 5, 6, 7])                                          # answer

        multi_qry_ans = ([[[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6]]],  # query
                             [4, 5, 6, 7])                                # answer

        for series, example in zip([single_dim_ts, multi_dim_ts], [single_qry_ans, multi_qry_ans]):

            data = series * 100
            n_dims = max([len(q) for q in data])
            timesteps = max([len(q[0]) for q in data])
            batch_size = 1

            encoder = RnnEncoder(encoded_vector_size=15, train_iters=10, ts_n_dims=n_dims)
            encoder.prepare_encoder(data, feedback_hoop_function=lambda x: print(x), batch_size=batch_size)
            encoded = encoder.encode(data)
            decoded = encoder.decode(encoded, steps=timesteps).tolist()

            equal = 0
            unequal = 0
            self.assertEqual(len(data), len(decoded))
            self.assertEqual(len(data[0]), len(decoded[0]))
            self.assertEqual(len(data[0][0]), len(decoded[0][0]))

            for i in range(len(data)):
                for d in range(n_dims):
                    for t in range(timesteps):
                        if round(decoded[i][d][t], 0) == round(data[i][d][t], 0):
                            equal += 1
                        else:
                            unequal += 1

            print(f'Decoder got {equal} correct and {unequal} incorrect')
            self.assertGreaterEqual(equal*2, unequal)

            error_margin = 3
            query, answer = example
            encoded_data, preds = encoder.encode(query, get_next_count=1)
            decoded_data = encoder.decode(encoded_data, steps=len(query[0][0])).tolist()

            # check prediction
            if len(data[0]) > 1:
                preds = torch.reshape(preds, (1, n_dims)).tolist()[-1]
            else:
                preds = preds.squeeze().tolist()

            for ans, pred in zip(answer, preds):
                self.assertGreater(error_margin, abs(pred - ans))

            # check reconstruction
            float_query = [list(map(float, q)) for q in query[0]]
            for qry, dec in zip(float_query, decoded_data[0]):
                for truth, pred in zip(qry, dec):
                    self.assertGreater(error_margin, abs(truth - pred))
