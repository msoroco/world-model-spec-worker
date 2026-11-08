"""Reversible proposed CARLA propulsion fault for C10052 clause (b).

This is an engineering impairment and readback protocol. A successful simulator
readback is not, by itself, a statutory disabled-vehicle finding.
"""
from __future__ import annotations
import copy
import math

FAULT_MAX_RPM=1.0

def validate_physics(physics):
    value=getattr(physics,'max_rpm',None)
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError('Native drivetrain max_rpm readback missing')
    return float(value)

def apply_fault(vehicle,enabled):
    """Return original physics for restoration after an exclusive Native attempt."""
    if type(enabled) is not bool:raise TypeError('Fault setting must be boolean')
    original=copy.deepcopy(vehicle.get_physics_control())
    baseline=validate_physics(original)
    if baseline<=1000:raise RuntimeError('Original drivetrain lacks healthy baseline')
    if enabled:
        modified=copy.deepcopy(original);modified.max_rpm=FAULT_MAX_RPM
        vehicle.apply_physics_control(modified)
    applied=validate_physics(vehicle.get_physics_control())
    if enabled and abs(applied-FAULT_MAX_RPM)>.1:
        raise RuntimeError('Native propulsion fault did not read back')
    if not enabled and abs(applied-baseline)>max(1,baseline*.001):
        raise RuntimeError('Healthy control drivetrain changed')
    return {'baseline_max_rpm':baseline,'applied_max_rpm':applied,
            'fault_commanded':enabled,'fault_readback':enabled and applied<=1.1,
            'legal_disability_verified':False},original

def restore(vehicle,original):
    vehicle.apply_physics_control(original)
    measured=validate_physics(vehicle.get_physics_control())
    expected=validate_physics(original)
    if abs(measured-expected)>max(1,expected*.001):
        raise RuntimeError('Original Native drivetrain restoration failed')
    return measured

if __name__=='__main__':
    class Physics:
        def __init__(self,max_rpm):self.max_rpm=max_rpm
    class Vehicle:
        def __init__(self):self.physics=Physics(5000)
        def get_physics_control(self):return self.physics
        def apply_physics_control(self,p):self.physics=p
    for enabled in (False,True):
        actor=Vehicle();readback,original=apply_fault(actor,enabled)
        assert readback['fault_readback'] is enabled
        assert restore(actor,original)==5000
    print('exception_b_native_cpu_protocol_passed')
