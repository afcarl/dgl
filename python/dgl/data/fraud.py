"""Fraud Dataset
"""
import os
from scipy import io
import numpy as np

from .utils import save_graphs, load_graphs, _get_dgl_url
from ..convert import heterograph
from ..utils import graphdata2tensors
from .dgl_dataset import DGLBuiltinDataset
from .. import backend as F


class FraudDataset(DGLBuiltinDataset):
    r"""Fraud node prediction dataset.

    The dataset includes two multi-relational graphs extracted from Yelp and Amazon
    where nodes represent fraudulent reviews or fraudulent reviewers.

    It was first proposed in a CIKM'20 paper <https://arxiv.org/pdf/2008.08692.pdf> and
    has been used by a recent WWW'21 paper <https://ponderly.github.io/pub/PCGNN_WWW2021.pdf>
    as a benchmark. Another paper <https://arxiv.org/pdf/2104.01404.pdf> also takes
    the dataset as an example to study the non-homophilous graphs. This dataset is built
    upon industrial data and has rich relational information and unique properties like
    class-imbalance and feature inconsistency, which makes the dataset be a good instance
    to investigate how GNNs perform on real-world noisy graphs. These graphs are bidirected
    and not self connected.

    Reference: <https://github.com/YingtongDou/CARE-GNN>

    Parameters
    ----------
    name : str
        Name of the dataset
    raw_dir : str
        Specifying the directory that will store the
        downloaded data or the directory that
        already stores the input data.
        Default: ~/.dgl/
    train_size : float
        training set size of the dataset.
        Default: 0.7
    val_size : float
        validation set size of the dataset, and the
        size of testing set is (1 - train_size - val_size)
        Default: 0.1

    Attributes
    ----------
    num_classes : int
        Number of label classes
    graph : dgl.heterograph.DGLHeteroGraph
        Graph structure, etc.
    train_size : float
        Training set size of the dataset.
    val_size : float
        Validation set size of the dataset

    Examples
    --------
    >>> dataset = FraudDataset('yelp')
    >>> graph = dataset[0]
    >>> num_classes = dataset.num_classes
    >>> feat = dataset.ndata['feature']
    >>> label = dataset.ndata['label']
    """
    file_urls = {
        'yelp': 'dataset/FraudYelp.zip',
        'amazon': 'dataset/FraudAmazon.zip'
    }
    relations = {
        'yelp': ['net_rsr', 'net_rtr', 'net_rur'],
        'amazon': ['net_upu', 'net_usu', 'net_uvu']
    }
    file_names = {
        'yelp': 'YelpChi.mat',
        'amazon': 'Amazon.mat'
    }
    node_name = {
        'yelp': 'user',
        'amazon': 'review'
    }

    def __init__(self, name, raw_dir=None, train_size=0.7, val_size=0.1):
        assert name in ['yelp', 'amazon'], "only supports 'yelp', or 'amazon'"
        url = _get_dgl_url(self.file_urls[name])
        self.train_size = train_size
        self.val_size = val_size
        super(FraudDataset, self).__init__(name=name,
                                           url=url,
                                           raw_dir=raw_dir)

    def process(self):
        """process raw data to graph, labels, splitting masks"""
        file_path = os.path.join(self.raw_path, self.file_names[self.name])

        data = io.loadmat(file_path)
        node_features = data['features'].todense()
        node_labels = data['label']

        graph_data = {}
        for relation in self.relations[self.name]:
            u, v, _, _ = graphdata2tensors(data[relation])
            graph_data[(self.node_name[self.name], relation, self.node_name[self.name])] = (u, v)
        g = heterograph(graph_data)

        g.ndata['feature'] = F.tensor(node_features)
        g.ndata['label'] = F.tensor(node_labels.T)
        self.graph = g

        self._random_split(g.ndata['feature'], g.ndata['label'], self.train_size, self.val_size)

    def __getitem__(self, idx):
        r""" Get graph object

        Parameters
        ----------
        idx : int
            Item index

        Returns
        -------
        :class:`dgl.heterograph.DGLHeteroGraph`
            graph structure, node features, node labels and masks

            - ``ndata['feature']``: node features
            - ``ndata['label']``: node labels
            - ``ndata['train_mask']``: mask of training set
            - ``ndata['val_mask']``: mask of validation set
            - ``ndata['test_mask']``: mask of testing set
        """
        assert idx == 0, "This dataset has only one graph"
        return self.graph

    def __len__(self):
        """number of data examples"""
        return len(self.graph)

    @property
    def num_classes(self):
        """Number of classes.

        Return
        -------
        int
        """
        return 2

    def save(self):
        """save processed data to directory `self.save_path`"""
        graph_path = os.path.join(self.save_path, self.name + '_dgl_graph.bin')
        save_graphs(str(graph_path), self.graph)

    def load(self):
        """load processed data from directory `self.save_path`"""
        graph_path = os.path.join(self.save_path, self.name + '_dgl_graph.bin')
        graph_list, _ = load_graphs(str(graph_path))
        g = graph_list[0]
        self.graph = g

    def has_cache(self):
        """check whether there are processed data in `self.save_path`"""
        graph_path = os.path.join(self.save_path, self.name + '_dgl_graph.bin')
        return os.path.exists(graph_path)

    def _random_split(self, x, train_size=0.7, val_size=0.1):
        """split the dataset into training set, validation set and testing set"""

        assert 0 <= train_size + val_size <= 1, \
            "The sum of valid training set size and validation set size " \
            "must between 0 and 1 (inclusive)."

        N = x.shape[0]
        index = list(range(N))
        if self.name == 'amazon':
            # 0-3304 are unlabeled nodes
            index = list(range(3305, N))

        np.random.permutation(index)
        train_idx = index[:int(train_size * N)]
        val_idx = index[int(N - val_size * N):]
        test_idx = index[int(train_size * N):int(N - val_size * N)]
        train_mask = np.zeros(N, dtype=np.bool)
        val_mask = np.zeros(N, dtype=np.bool)
        test_mask = np.zeros(N, dtype=np.bool)
        train_mask[train_idx] = True
        val_mask[val_idx] = True
        test_mask[test_idx] = True
        self.graph.ndata['train_mask'] = F.tensor(train_mask)
        self.graph.ndata['val_mask'] = F.tensor(val_mask)
        self.graph.ndata['test_mask'] = F.tensor(test_mask)


class FraudYelpDataset(FraudDataset):
    r""" Fraud Yelp Dataset

    The Yelp dataset includes hotel and restaurant reviews filtered (spam) and recommended
    (legitimate) by Yelp. A spam review detection task can be conducted, which is a binary
    classification task. 32 handcrafted features from
    <http://dx.doi.org/10.1145/2783258.2783370> are taken as the raw node features. Reviews
    are nodes in the graph, and three relations are:
        1. R-U-R: it connects reviews posted by the same user
        2. R-S-R: it connects reviews under the same product with the same star rating (1-5 stars)
        3. R-T-R: it connects two reviews under the same product posted in the same month.

    Statistics:

    - Nodes: 45,954
    - Edges:
        R-U-R: 49,315
        R-T-R: 573,616
        R-S-R: 3,402,743
        ALL: 3,846,979
    - Classes:
        Positive (spam): 6,677
        Negative (legitimate): 39,277
    - Positive-Negative ratio: 1 : 5.9
    - Node feature size: 32

    Parameters
    ----------
    raw_dir : str
        Specifying the directory that will store the
        downloaded data or the directory that
        already stores the input data.
        Default: ~/.dgl/
    train_size : float
        training set size of the dataset.
        Default: 0.7
    val_size : float
        validation set size of the dataset, and the
        size of testing set is (1 - train_size - val_size)
        Default: 0.1

    Examples
    --------
    >>> dataset = FraudYelpDataset()
    >>> graph = dataset[0]
    >>> num_classes = dataset.num_classes
    >>> feat = dataset.ndata['feature']
    >>> label = dataset.ndata['label']
    """

    def __init__(self, raw_dir=None, train_size=0.7, val_size=0.1):
        super(FraudYelpDataset, self).__init__(name='yelp',
                                               raw_dir=raw_dir,
                                               train_size=train_size,
                                               val_size=val_size)


class FraudAmazonDataset(FraudDataset):
    r""" Fraud Amazon Dataset

    The Amazon dataset includes product reviews under the Musical Instruments category.
    Users with more than 80% helpful votes are labelled as benign entities and users with
    less than 20% helpful votes are labelled as fraudulent entities. A fraudulent user
    detection task can be conducted on the Amazon dataset, which is a binary classification
    task. 25 handcrafted features from <https://arxiv.org/pdf/2005.10150.pdf> are taken as
    the raw node features .

    Users are nodes in the graph, and three relations are:
        1. U-P-U : it connects users reviewing at least one same product
        2. U-S-U : it connects users having at least one same star rating within one week
        3. U-V-U : it connects users with top 5% mutual review text similarities (measured by
                   TF-IDF) among all users.

    Statistics:

    - Nodes: 11,944
    - Edges:
        U-P-U: 175,608
        U-S-U: 3,566,479
        U-V-U: 1,036,737
        ALL: 4,398,392
    - Classes:
        Positive (fraudulent): 821
        Negative (benign): 11,123
    - Positive-Negative ratio: 1 : 13.5
    - Node feature size: 25

    Parameters
    ----------
    raw_dir : str
        Specifying the directory that will store the
        downloaded data or the directory that
        already stores the input data.
        Default: ~/.dgl/
    train_size : float
        training set size of the dataset.
        Default: 0.7
    val_size : float
        validation set size of the dataset, and the
        size of testing set is (1 - train_size - val_size)
        Default: 0.1

    Examples
    --------
    >>> dataset = FraudAmazonDataset()
    >>> graph = dataset[0]
    >>> num_classes = dataset.num_classes
    >>> feat = dataset.ndata['feature']
    >>> label = dataset.ndata['label']
    """

    def __init__(self, raw_dir=None, train_size=0.7, val_size=0.1):
        super(FraudAmazonDataset, self).__init__(name='amazon',
                                                 raw_dir=raw_dir,
                                                 train_size=train_size,
                                                 val_size=val_size)
