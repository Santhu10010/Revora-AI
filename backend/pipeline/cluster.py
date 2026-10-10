"""Clustering of similar clauses."""
from typing import List, Tuple
from backend.schemas import ClauseRecord, ClusterRecord
import numpy as np


EMBEDDING_MODEL = None  # Lazy-loaded for full mode


def load_embedding_model():
    """Lazy-load multilingual embedding model for full mode."""
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is not None:
        return EMBEDDING_MODEL

    try:
        from sentence_transformers import SentenceTransformer
        EMBEDDING_MODEL = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        return EMBEDDING_MODEL
    except Exception as e:
        print(f"Failed to load embedding model: {e}")
        return None


def compute_embeddings(texts: List[str], model) -> np.ndarray:
    """Compute embeddings for a list of texts."""
    if model is None:
        return None
    try:
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings
    except Exception:
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def cluster_clauses(clause_list: List[ClauseRecord], mode: str = 'lite') -> Tuple[List[ClusterRecord], List[ClauseRecord]]:
    """
    Cluster clauses by aspect and polarity.
    Lite mode: simple keyword similarity (Jaccard)
    Full mode: multilingual embeddings (cosine similarity)
    """
    if not clause_list:
        return [], clause_list

    # Load embedding model if full mode
    embedding_model = None
    if mode == 'full':
        embedding_model = load_embedding_model()

    # Group by aspect and polarity
    groups = {}
    for clause in clause_list:
        key = (clause.aspect or 'other', clause.polarity)
        if key not in groups:
            groups[key] = []
        groups[key].append(clause)

    cluster_list = []
    cluster_id_counter = 0

    for (aspect, polarity), clauses_in_group in groups.items():
        if len(clauses_in_group) < 2:
            # Single clause, assign to its own cluster
            cluster_id = f"cluster_{cluster_id_counter}"
            cluster = ClusterRecord(
                cluster_id=cluster_id,
                aspect=aspect if aspect != 'other' else None,
                polarity=polarity,
                label=aspect or 'Other',
                example_clause_id=clauses_in_group[0].clause_id,
                size=1
            )
            cluster_list.append(cluster)
            clauses_in_group[0].cluster_id = cluster_id
            cluster_id_counter += 1
            continue

        # Clustering
        if mode == 'full' and embedding_model:
            # Use embeddings
            clusters = cluster_by_embeddings(clauses_in_group, embedding_model)
        else:
            # Use Jaccard similarity
            clusters = simple_cluster_by_similarity(clauses_in_group)

        # Create cluster records
        for sub_clauses in clusters:
            cluster_id = f"cluster_{cluster_id_counter}"
            cluster = ClusterRecord(
                cluster_id=cluster_id,
                aspect=aspect if aspect != 'other' else None,
                polarity=polarity,
                label=generate_cluster_label(sub_clauses),
                example_clause_id=sub_clauses[0].clause_id,
                size=len(sub_clauses)
            )
            cluster_list.append(cluster)

            # Assign clauses to cluster
            for clause in sub_clauses:
                clause.cluster_id = cluster_id

            cluster_id_counter += 1

    return cluster_list, clause_list


def cluster_by_embeddings(clauses: List[ClauseRecord], model) -> List[List[ClauseRecord]]:
    """Cluster using embeddings and cosine similarity."""
    if len(clauses) < 2:
        return [clauses]

    texts = [c.clause_text for c in clauses]
    embeddings = compute_embeddings(texts, model)

    if embeddings is None:
        return [clauses]

    # Greedy clustering: start with first embedding, add similar ones
    clusters = []
    assigned = set()
    threshold = 0.4

    for i, emb_i in enumerate(embeddings):
        if i in assigned:
            continue

        cluster = [clauses[i]]
        assigned.add(i)

        # Find similar embeddings
        for j in range(i + 1, len(embeddings)):
            if j in assigned:
                continue

            emb_j = embeddings[j]
            similarity = cosine_similarity(emb_i, emb_j)

            if similarity > threshold:
                cluster.append(clauses[j])
                assigned.add(j)

        clusters.append(cluster)

    return clusters


def simple_cluster_by_similarity(clauses: List[ClauseRecord]) -> List[List[ClauseRecord]]:
    """
    Simple clustering: group clauses that share keywords.
    """
    if len(clauses) < 2:
        return [clauses]

    # Extract words from each clause
    clause_words = []
    for clause in clauses:
        words = set(c.lower() for c in clause.clause_text.split() if len(c) > 2)
        clause_words.append(words)

    # Greedy clustering: start with first clause, add similar ones
    clusters = []
    assigned = set()

    for i, words_i in enumerate(clause_words):
        if i in assigned:
            continue

        cluster = [clauses[i]]
        assigned.add(i)

        # Find similar clauses
        for j in range(i + 1, len(clause_words)):
            if j in assigned:
                continue

            words_j = clause_words[j]
            # Simple similarity: Jaccard index
            if len(words_i | words_j) > 0:
                similarity = len(words_i & words_j) / len(words_i | words_j)
                if similarity > 0.3:
                    cluster.append(clauses[j])
                    assigned.add(j)

        clusters.append(cluster)

    return clusters


def generate_cluster_label(clauses: List[ClauseRecord]) -> str:
    """Generate a label for a cluster based on common terms."""
    if not clauses:
        return 'Unknown'

    # Extract common words from all clauses
    all_words = []
    for clause in clauses:
        words = clause.clause_text.lower().split()
        all_words.extend(words)

    # Count word frequencies (exclude common words)
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                    'should', 'may', 'might', 'must', 'can', 'and', 'or', 'but', 'in',
                    'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about',
                    'into', 'through', 'during', 'before', 'after', 'above', 'below',
                    'until', 'between', 'under', 'again', 'further', 'then', 'once',
                    'that', 'this', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
                    'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
                    'nahi', 'nhi', 'nahin', 'hai', 'hain', 'ka', 'ki', 'ke', 'aur', 'par'}

    word_counts = {}
    for word in all_words:
        if len(word) > 2 and word not in common_words:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Get top 2 words
    top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:2]
    label = ' '.join([w[0] for w in top_words])

    return label if label else 'Other'
