"""AI Parking Engine - ML models for smart parking recommendations.

Provides three core AI components:
1. ParkingTopology - Virtual parking lot topology modeling
2. TrafficPredictor - Time-series traffic flow prediction (MLP)
3. CollaborativeSpotRecommender - User-based collaborative filtering for spot recommendations
"""

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from sklearn.neural_network import MLPRegressor


class ParkingTopology:
    """Models the virtual parking lot topology with 5 groups (A-E), 20 spots each."""

    def __init__(self):
        self.total_virtual_spots = 100
        self.start_id = 3
        self.groups = ['A', 'B', 'C', 'D', 'E']
        self.spots_map = self._build_topology()

    def _build_topology(self):
        """Build a dictionary mapping groups to their spot ID ranges.

        Returns:
            dict: {group: {'row_1': [ids], 'row_2': [ids], 'all_spots': [ids]}}
        """
        topology = {}
        current_id = self.start_id
        for group in self.groups:
            topology[group] = {
                'row_1': list(range(current_id, current_id + 10)),
                'row_2': list(range(current_id + 10, current_id + 20)),
                'all_spots': list(range(current_id, current_id + 20))
            }
            current_id += 20
        return topology


class TrafficPredictor:
    """Predicts future parking occupancy using an MLP neural network.

    Trains on historical occupancy data sequences and predicts the next
    time step using a sliding window approach.
    """

    def __init__(self, sequence_length=12):
        self.sequence_length = sequence_length
        self.model = MLPRegressor(
            hidden_layer_sizes=(50, 25),
            activation='relu',
            max_iter=1000,
            random_state=42
        )
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.is_trained = False

    def train(self, historical_data):
        """Train the model on historical occupancy data.

        Args:
            historical_data (list): List of occupancy values over time.
        """
        scaled_data = self.scaler.fit_transform(np.array(historical_data).reshape(-1, 1))
        X, y = [], []
        for i in range(self.sequence_length, len(scaled_data)):
            X.append(scaled_data[i - self.sequence_length:i, 0])
            y.append(scaled_data[i, 0])
        if len(X) > 0:
            self.model.fit(np.array(X), np.array(y))
            self.is_trained = True

    def predict_next_step(self, recent_data):
        """Predict the next occupancy value given recent history.

        Args:
            recent_data (list): Last N occupancy values (N = sequence_length).

        Returns:
            float: Predicted occupancy value.
        """
        if not self.is_trained:
            return float(np.mean(recent_data)) if recent_data else 0.0
        scaled_recent = self.scaler.transform(np.array(recent_data).reshape(-1, 1))
        predicted_scaled = self.model.predict(scaled_recent.reshape(1, self.sequence_length))
        return float(self.scaler.inverse_transform(predicted_scaled.reshape(-1, 1))[0][0])


class CollaborativeSpotRecommender:
    """Recommends parking spots using user-based collaborative filtering.

    Uses NearestNeighbors with cosine similarity to find similar users
    and aggregate their parking preferences to rank available spots.
    """

    def __init__(self):
        self.model = NearestNeighbors(metric='cosine', algorithm='brute')
        self.user_item_matrix = None
        self.user_ids = []

    def fit_history(self, parking_history_df):
        """Fit the recommendation model on historical parking preference data.

        Args:
            parking_history_df (pd.DataFrame): DataFrame with columns
                user_id, spot_id, rating.
        """
        pivot_table = parking_history_df.pivot(
            index='user_id', columns='spot_id', values='rating'
        ).fillna(0)
        self.user_item_matrix = pivot_table.values
        self.user_ids = list(pivot_table.index)
        self.model.fit(self.user_item_matrix)

    def recommend(self, user_id, available_spots, n_recommendations=3, is_green=False):
        """Recommend top-N parking spots for a user.

        Args:
            user_id (int): The user to recommend for.
            available_spots (list[int]): Currently free spot IDs.
            n_recommendations (int): Number of recommendations to return.
            is_green (bool): Whether the vehicle has a green (new energy) plate.
                Green plates have access to A-zone charging spots (3-22).

        Returns:
            list: Top N recommended spot IDs.
        """
        # Green-plate filter: exclude charging zone (3-22) for non-green plates
        if not is_green:
            available_spots = [s for s in available_spots if s > 22]

        if user_id not in self.user_ids or not available_spots:
            return sorted(available_spots)[:n_recommendations]

        user_idx = self.user_ids.index(user_id)
        distances, indices = self.model.kneighbors(
            self.user_item_matrix[user_idx].reshape(1, -1),
            n_neighbors=min(6, len(self.user_ids))
        )
        similar_users_indices = indices.flatten()[1:]

        if len(similar_users_indices) == 0:
            return sorted(available_spots)[:n_recommendations]

        aggregated_preferences = np.mean(self.user_item_matrix[similar_users_indices], axis=0)
        scored_spots = []
        for i, spot in enumerate(range(3, 103)):
            if spot in available_spots and i < len(aggregated_preferences):
                scored_spots.append((spot, aggregated_preferences[i]))

        scored_spots.sort(key=lambda x: x[1], reverse=True)
        if scored_spots:
            return [s[0] for s in scored_spots[:n_recommendations]]
        return sorted(available_spots)[:n_recommendations]
