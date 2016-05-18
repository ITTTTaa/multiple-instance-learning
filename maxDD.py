
import numpy as np
import scipy.optimize as optimize
import random
from sklearn import cross_validation
from data_utils import load_musk1_data


_floatX = np.float32
_intX = np.int8

class DiverseDensity(object):
    """
    bags is a list of bag
    each bag is a dict required following <key, value>
    key: inst_prob, value: a vector indicating each instance's probability
    key: label, value: a scalar indicating this bag's label
    key: prob, value: a scalar indicating this bag's probability
    key: instances, value: a numpy array indicating instances in this bag, each row is a instance, each colum is a
    feature
    """

    def __init__(self):
        pass

    def diverse_density_nll(self, params, bags):

        fun = 0
        n_bag = len(bags)
        n_dim = bags[0]['instances'].shape[1]
        # parameter length equal to feature length, only learn target vector
        if params.shape[0] == n_dim:
            target = params
            scale = np.ones(n_dim, )
        # parameter length equal to 2*feature length, learn target vector and scaling vector both
        else:
            target = params[0:n_dim]
            scale = params[n_dim:]

        # compute negative log likelihood
        for bag_idx in range(n_bag):
            instances = bags[bag_idx]['instances']
            dist = np.mean(((instances - target) ** 2) * (scale ** 2), axis=1)
            bags[bag_idx]['inst_prob'] = np.exp(-dist)
            bags[bag_idx]['prob'] = 1 - np.prod(1 - np.asarray(bags[bag_idx]['inst_prob']))

            if bags[bag_idx]['label'] == 1:
                if bags[bag_idx]['prob'] == 0:
                    bags[bag_idx]['prob'] = 1e-10
                fun = fun - np.log(bags[bag_idx]['prob'])
            else:
                if bags[bag_idx]['prob'] == 1:
                    bags[bag_idx]['prob'] = 1 - 1e-10
                fun = fun - np.log(1 - bags[bag_idx]['prob'])
        return fun

    def train(self, bags, scale_indicator, epochs):

        n_bag = len(bags)

        n_pos_bag = 0
        max_iter = 0
        for bag in bags:
            if bag['label'] == 1:
                n_pos_bag += 1
                max_iter += bag['instances'].shape[0]
        print('number of training positive bags is %d, number of positive instances is: %d' % (n_pos_bag, max_iter))

        epochs = min(max_iter, epochs)
        print('total epochs number is %d' % epochs)

        targets = list()
        scales = list()
        func_values = list()

        for epoch_idx in range(epochs):
            bag_idx = random.randint(0, n_bag - 1)
            while bags[bag_idx]['label'] == 0 or np.all(np.asarray(bags[bag_idx]['starting_point']) == 1):
                bag_idx = random.randint(0, n_bag - 1)

            [n_instances, n_dim] = bags[bag_idx]['instances'].shape
            starting_point_bag = np.asarray(bags[bag_idx]['starting_point'])
            valuable_idx = np.asarray(np.nonzero(starting_point_bag == 0))
            if valuable_idx.shape[1] == 1:
                instance_idx = valuable_idx[0, 0]
            else:
                rand_idx = random.randint(0, valuable_idx.shape[1]-1)
                instance_idx = valuable_idx[0, rand_idx]
            bags[bag_idx]['starting_point'][instance_idx] = 1

            if scale_indicator == 1:
                init_params = np.hstack((bags[bag_idx]['instances'][instance_idx, :], np.ones([n_dim, ])))
                r_params = optimize.minimize(self.diverse_density_nll, init_params, args=(bags,), method='L-BFGS-B')
                print('epoch %d, selected instance is from <bag %d, bag label %d, instance %d>. '
                      'nll before optimization is %f, nll after optimization is %f' %
                      (epoch_idx, bag_idx, bags[bag_idx]['label'], instance_idx,
                       self.diverse_density_nll(init_params, bags),
                       self.diverse_density_nll(r_params.x, bags)))
                targets.append(r_params.x[:n_dim])
                scales.append(r_params.x[n_dim:])
                func_values.append(r_params.fun)

            else:
                init_params = bags[bag_idx]['instances'][instance_idx, :]
                r_params = optimize.minimize(self.diverse_density_nll, init_params, args=(bags,), method='L-BFGS-B')
                print('epoch %d, selected instance is from <bag %d, bag label %d, instance %d>. '
                      'nll before optimization is %f, nll after optimization is %f' %
                      (epoch_idx, bag_idx, bags[bag_idx]['label'], instance_idx,
                       self.diverse_density_nll(init_params, bags),
                       self.diverse_density_nll(r_params.x, bags)))
                targets.append(r_params.x)
                scales.append(np.ones(n_dim,))
                func_values.append(r_params.fun)
        return targets, scales, func_values

    def predict(self, targets, scales, fvals, bags, aggregate, threshold):

        n_bag = len(bags)

        bags_label = np.zeros(n_bag, )
        bags_prob = np.zeros(n_bag, )
        instances_prob = list()
        instances_label = list()

        fvals = np.asarray(fvals)
        targets = np.asarray(targets)
        scales = np.asarray(scales)
        # with minimum diverse density
        if aggregate == 'max':
            target_idx = np.argmax(fvals)
            target = targets[target_idx]
            scale = scales[target_idx]
        # with maximum diverse density
        elif aggregate == 'min':
            target_idx = np.argmin(fvals)
            target = targets[target_idx]
            scale = scales[target_idx]
        # with average diverse density
        elif aggregate == 'avg':
            target = np.mean(targets, axis=0)
            scale = np.mean(scales, axis=0)
        else:
            raise NotImplementedError('must be max, min or avg')

        for bag_idx in range(n_bag):
            instances = bags[bag_idx]['instances']
            dist = np.mean(((instances - target) ** 2) * (scale ** 2), axis=1)
            inst_prob = np.exp(-dist)
            inst_label = np.int8(inst_prob > threshold)
            bags_prob[bag_idx] = np.max(inst_prob)
            bags_label[bag_idx] = np.any(inst_label)
            instances_prob.append(inst_prob)
            instances_label.append(inst_label)

        return bags_label, bags_prob, instances_label, instances_prob


def toy_example():

    dd_classifier = DiverseDensity()

    train_bags = list()
    train_labels = list()

    n_dim = random.randint(5, 10)
    n_train_bags = random.randint(20, 100)

    n_positive_bag = 0
    n_negative_bag = 0
    idx = 0

    while idx < n_train_bags:
        bag = dict()
        if random.random() < 0.5:
            mu = 10
            sig = 1.0
            bag['label'] = 1
            train_labels.append(1)
            bag['prob'] = 0
            n_instances = np.random.randint(1, 20)
            bag['inst_prob'] = np.random.random([n_instances, ])
            bag['starting_point'] = np.zeros([n_instances, ])
            bag['instances'] = np.random.normal(mu, sig, [n_instances, n_dim])
            train_bags.append(bag)
            idx += 1
            n_positive_bag += 1
        else:
            mu = 0.0
            sig = 1.0
            bag['label'] = 0
            train_labels.append(0)
            bag['prob'] = 0
            n_instances = np.random.randint(1, 20)
            bag['inst_prob'] = np.random.random([n_instances, ])
            bag['starting_point'] = np.zeros([n_instances, ])
            bag['instances'] = np.random.normal(mu, sig, [n_instances, n_dim])
            train_bags.append(bag)
            idx += 1
            n_negative_bag += 1

    print('positive bags number is:', n_positive_bag)
    print('negative bags number is: ', n_negative_bag)

    idx = 0
    n_test_bags = random.randint(10, 30)
    test_bags = list()
    test_labels = list()

    while idx < n_test_bags:
        bag = dict()
        if random.random() > 0.5:
            mu = 10
            sig = 1.0
            bag['label'] = 1
            test_labels.append(1)
            bag['prob'] = 0
            n_instances = np.random.randint(1, 20)
            bag['inst_prob'] = np.random.random([n_instances, ])
            bag['starting_point'] = np.zeros([n_instances, ])
            bag['instances'] = np.random.normal(mu, sig, [n_instances, n_dim])
            test_bags.append(bag)
            idx += 1
        else:
            mu = 0.0
            sig = 1.0
            bag['label'] = 0
            test_labels.append(0)
            bag['prob'] = 0
            n_instances = np.random.randint(1, 20)
            bag['inst_prob'] = np.random.random([n_instances, ])
            bag['starting_point'] = np.zeros([n_instances, ])
            bag['instances'] = np.random.normal(mu, sig, [n_instances, n_dim])
            test_bags.append(bag)
            idx += 1

    print('test bags number is:', n_test_bags)

    targets, scales, fvals = dd_classifier.train(train_bags, scale_indicator=1, epochs=1)

    aggregate = 'max'
    threshold = 0.5

    p_bags_label, p_bags_prob, p_instances_label, p_instances_prob = dd_classifier.predict(targets, scales,
                                                                                           fvals, test_bags,
                                                                                           aggregate, threshold)
    print('testing accuracy is: %f' % (sum(test_labels == p_bags_label)/n_test_bags))


def maxDD_musk1(split_ratio=None, cv_fold=None, aggregate='avg', threshold=0.5, scale_indicator=1, epochs=10):
    dd_classifier = DiverseDensity()
    file_path = 'musk1.txt'
    bags, bag_labels = load_musk1_data(file_path)
    if split_ratio is None and cv_fold is None:
        targets, scales, fvals = dd_classifier.train(bags, scale_indicator, epochs)
        p_bags_label, p_bags_prob, p_instances_label, p_instances_prob = dd_classifier.predict(targets, scales,
                                                                                               fvals, bags,
                                                                                               aggregate, threshold)
        accuracy = sum(bag_labels == p_bags_label) / len(bags)
        print('split ratio is %f, training accuracy is: %f' % (split_ratio, accuracy))

        train_result = (targets, scales, fvals)
        predict_result = (p_bags_label, p_bags_prob, p_instances_label, p_instances_prob)
        data = (bags, bag_labels)
        return data, train_result, predict_result

    elif split_ratio:
        train_bag, test_bag, train_label, test_label = cross_validation.train_test_split(bags,
                                                                                         bag_labels,
                                                                                         test_size=split_ratio,
                                                                                         random_state=0)

        targets, scales, fvals = dd_classifier.train(train_bag, scale_indicator, epochs)
        p_bags_label, p_bags_prob, p_instances_label, p_instances_prob = dd_classifier.predict(targets, scales,
                                                                                               fvals, test_bag,
                                                                                               aggregate, threshold)
        accuracy = sum(test_label == p_bags_label) / len(test_bag)
        print('testing accuracy with split ratio %f is: %f' % (split_ratio, accuracy))

        train_result = (targets, scales, fvals)
        predict_result = (p_bags_label, p_bags_prob, p_instances_label, p_instances_prob)
        data = (bags, bag_labels)
        return data, train_result, predict_result
    elif cv_fold:
        accuracy_list = list()
        n_bags = len(bags)
        kf = cross_validation.KFold(n_bags, cv_fold, shuffle=True, random_state=0)
        cf = 1
        for train_idx, test_idx in kf:
            train_bag = list()
            train_label = list()
            for idx in train_idx:
                train_bag.append(bags[idx])
                train_label.append(bag_labels[idx])
            test_bag = list()
            test_label = list()
            for idx in test_idx:
                test_bag.append(bags[idx])
                test_label.append(bag_labels[idx])

            targets, scales, fvals = dd_classifier.train(train_bag, scale_indicator, epochs)
            p_bags_label, p_bags_prob, p_instances_label, p_instances_prob = dd_classifier.predict(targets, scales,
                                                                                                   fvals, test_bag,
                                                                                                   aggregate, threshold)
            accuracy = sum(test_label == p_bags_label) / len(test_bag)
            accuracy_list.append(accuracy)
            print('current fold: %d, accuracy is: %f' % (cf, accuracy))
            cf += 1

        mean_accuracy = float(np.mean(np.asarray(accuracy_list)))
        print('mean accuracy with %d-fold cross validation is: %f' % (cv_fold, mean_accuracy))

        return accuracy_list
    else:
        pass


if __name__ == '__main__':
    # toy_example()
    maxDD_musk1(split_ratio=0.2, cv_fold=None, aggregate='min', threshold=0.5, scale_indicator=1, epochs=1)