#!/usr/bin/env python
# ----------------------------------------------------------------------------
# Copyright 2016 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""
CIFAR10 MLP with spelled out neon model framework in one file

The motivation is to show the flexibility of ngraph and how user can build a
model without the neon architecture. This may also help with debugging.

Run it using

python examples/cifar10/cifar10_mlp.py --data_dir /usr/local/data/CIFAR10 --output_file out.hd5

"""
from __future__ import division
from __future__ import print_function
import numpy as np
import ngraph as ng
from ngraph.frontends.neon import Affine, Preprocess, Sequential
from ngraph.frontends.neon import UniformInit, Rectlin, Softmax, GradientDescentMomentum
from ngraph.frontends.neon import ax, loop_train, make_bound_computation, make_default_callbacks
from ngraph.frontends.neon import NgraphArgparser
from ngraph.frontends.neon import ArrayIterator

from cifar10 import CIFAR10
import ngraph.transformers as ngt

parser = NgraphArgparser(description='Train simple mlp on cifar10 dataset')
args = parser.parse_args()

np.random.seed(args.rng_seed)

# Create the dataloader
train_data, valid_data = CIFAR10(args.data_dir).load_data()
train_set = ArrayIterator(train_data, args.batch_size, total_iterations=args.num_iterations)
valid_set = ArrayIterator(valid_data, args.batch_size)

inputs = train_set.make_placeholders()
ax.Y.length = 10

######################
# Model specification

def cifar_mean_subtract(x):
    bgr_mean = ng.persistent_tensor(
        axes=x.axes.find_by_short_name('channel'),
        initial_value=np.array([[104., 119., 127.]]))
    return (x - bgr_mean) / 255.

seq1 = Sequential([Preprocess(functor=cifar_mean_subtract),
                   Affine(nout=200, weight_init=UniformInit(-0.1, 0.1), activation=Rectlin()),
                   Affine(axes=ax.Y, weight_init=UniformInit(-0.1, 0.1), activation=Softmax())])

optimizer = GradientDescentMomentum(0.1, 0.9)
output_prob = seq1.train_outputs(inputs['image'])
errors = ng.not_equal(ng.argmax(output_prob, out_axes=[ax.N]), inputs['label'])
loss = ng.cross_entropy_multi(output_prob, ng.one_hot(inputs['label'], axis=ax.Y))
mean_cost = ng.mean(loss, out_axes=())
updates = optimizer(loss)

train_outputs = dict(batch_cost=mean_cost, updates=updates)
loss_outputs = dict(cross_ent_loss=loss, misclass_pct=errors)

# Now bind the computations we are interested in
transformer = ngt.make_transformer()
train_computation = make_bound_computation(transformer, train_outputs, inputs)
loss_computation = make_bound_computation(transformer, loss_outputs, inputs)

cbs = make_default_callbacks(output_file=args.output_file,
                             frequency=args.iter_interval,
                             train_computation=train_computation,
                             total_iterations=args.num_iterations,
                             eval_set=valid_set,
                             loss_computation=loss_computation,
                             use_progress_bar=args.progress_bar)

loop_train(train_set, train_computation, cbs)
